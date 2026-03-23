"""Preflight domain checks — fast pre-validation before full blockcheck.

Runs 4 quick checks per domain in parallel:
1. DNS resolution + IP blocklist match
2. TCP :443 connectivity
3. ICMP ping
4. HTTP GET :80 (ISP injection detection)

Results are informational; the full blockcheck continues regardless unless
the user opts to skip failed domains via the UI checkbox.
"""

from __future__ import annotations

import logging
import socket
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

from blockcheck.config import (
    DEFAULT_PARALLEL,
    KNOWN_BLOCK_IPS,
    PREFLIGHT_DNS_TIMEOUT,
    PREFLIGHT_HTTP_TIMEOUT,
    PREFLIGHT_PING_COUNT,
    PREFLIGHT_PING_TIMEOUT,
    PREFLIGHT_TCP_TIMEOUT,
)
from blockcheck.isp_page_detector import check_http_injection
from blockcheck.models import (
    PreflightResult,
    PreflightVerdict,
    SingleTestResult,
    TestStatus,
    TestType,
)
from blockcheck.ping_tester import ping_host

if TYPE_CHECKING:
    from collections.abc import Callable

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def _check_dns(domain: str, timeout: float = PREFLIGHT_DNS_TIMEOUT) -> SingleTestResult:
    """Resolve domain via system DNS and check against known block IPs.

    Note: socket.getaddrinfo() does not natively support timeouts.
    We set a default socket timeout for the duration of the call.
    """
    start = time.time()
    old_timeout = socket.getdefaulttimeout()
    try:
        socket.setdefaulttimeout(timeout)
        results = socket.getaddrinfo(domain, 443, socket.AF_UNSPEC, socket.SOCK_STREAM)
        elapsed = (time.time() - start) * 1000

        if not results:
            return SingleTestResult(
                target_name=domain, test_type=TestType.PREFLIGHT_DNS,
                status=TestStatus.FAIL, error_code="NO_RECORDS",
                time_ms=round(elapsed, 2),
                detail="DNS returned no records",
            )

        ips = sorted({addr[4][0] for addr in results})
        blocked = [ip for ip in ips if ip in KNOWN_BLOCK_IPS]

        if blocked:
            return SingleTestResult(
                target_name=domain, test_type=TestType.PREFLIGHT_DNS,
                status=TestStatus.FAIL, error_code="BLOCK_IP",
                time_ms=round(elapsed, 2),
                detail=f"Block IP: {', '.join(blocked)}",
                raw_data={"ips": ips, "blocked": blocked},
            )

        return SingleTestResult(
            target_name=domain, test_type=TestType.PREFLIGHT_DNS,
            status=TestStatus.OK, time_ms=round(elapsed, 2),
            detail=f"OK ({', '.join(ips)})",
            raw_data={"ips": ips},
        )

    except socket.gaierror as e:
        return SingleTestResult(
            target_name=domain, test_type=TestType.PREFLIGHT_DNS,
            status=TestStatus.FAIL, error_code="DNS_FAIL",
            time_ms=round((time.time() - start) * 1000, 2),
            detail=f"DNS error: {e}",
        )
    except socket.timeout:
        return SingleTestResult(
            target_name=domain, test_type=TestType.PREFLIGHT_DNS,
            status=TestStatus.TIMEOUT, error_code="DNS_TIMEOUT",
            time_ms=round((time.time() - start) * 1000, 2),
            detail="DNS resolution timeout",
        )
    except Exception as e:
        return SingleTestResult(
            target_name=domain, test_type=TestType.PREFLIGHT_DNS,
            status=TestStatus.ERROR, error_code="ERROR",
            time_ms=round((time.time() - start) * 1000, 2),
            detail=str(e)[:100],
        )
    finally:
        socket.setdefaulttimeout(old_timeout)


def _check_tcp_443(domain: str, resolved_ip: str | None = None,
                   timeout: float = PREFLIGHT_TCP_TIMEOUT) -> SingleTestResult:
    """Try TCP connect to port 443."""
    host = resolved_ip or domain
    start = time.time()
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.settimeout(timeout)
        err = sock.connect_ex((host, 443))
        elapsed = (time.time() - start) * 1000

        if err == 0:
            return SingleTestResult(
                target_name=domain, test_type=TestType.PREFLIGHT_TCP,
                status=TestStatus.OK, time_ms=round(elapsed, 2),
                detail=f"TCP :443 open ({host})",
            )
        return SingleTestResult(
            target_name=domain, test_type=TestType.PREFLIGHT_TCP,
            status=TestStatus.FAIL, error_code=f"ERR_{err}",
            time_ms=round(elapsed, 2),
            detail=f"TCP :443 connect failed (errno={err})",
        )
    except socket.timeout:
        return SingleTestResult(
            target_name=domain, test_type=TestType.PREFLIGHT_TCP,
            status=TestStatus.TIMEOUT, error_code="TIMEOUT",
            time_ms=round((time.time() - start) * 1000, 2),
            detail="TCP :443 timeout",
        )
    except Exception as e:
        return SingleTestResult(
            target_name=domain, test_type=TestType.PREFLIGHT_TCP,
            status=TestStatus.ERROR, error_code="ERROR",
            time_ms=round((time.time() - start) * 1000, 2),
            detail=str(e)[:100],
        )
    finally:
        sock.close()


def _check_http_get(domain: str) -> SingleTestResult:
    """Quick HTTP GET on port 80 to detect ISP injection/redirect."""
    # check_http_injection always returns a fresh SingleTestResult, safe to mutate
    result = check_http_injection(domain, timeout=PREFLIGHT_HTTP_TIMEOUT)
    result.test_type = TestType.PREFLIGHT_HTTP
    return result


# ---------------------------------------------------------------------------
# Per-domain orchestration
# ---------------------------------------------------------------------------

def _check_one_domain(domain: str) -> PreflightResult:
    """Run all 4 preflight checks for a single domain."""
    pf = PreflightResult(domain=domain)

    # 1. DNS resolution + IP blocklist
    dns_r = _check_dns(domain)
    pf.dns_result = dns_r
    if dns_r.raw_data.get("ips"):
        pf.resolved_ips = dns_r.raw_data["ips"]
    if dns_r.error_code == "BLOCK_IP":
        pf.is_block_ip = True
        pf.block_ip_detail = dns_r.detail

    # Pick first resolved IPv4 for TCP check
    first_ipv4 = None
    for ip in pf.resolved_ips:
        if ":" not in ip:  # skip IPv6
            first_ipv4 = ip
            break

    # 2-4 run in parallel: TCP, Ping, HTTP GET
    with ThreadPoolExecutor(max_workers=3) as pool:
        tcp_future = pool.submit(_check_tcp_443, domain, first_ipv4)
        ping_future = pool.submit(
            ping_host, domain,
            count=PREFLIGHT_PING_COUNT, timeout=PREFLIGHT_PING_TIMEOUT,
        )
        http_future = pool.submit(_check_http_get, domain)

        pf.tcp_443 = tcp_future.result()
        pf.ping = ping_future.result()
        pf.http_check = http_future.result()

    # Compute verdict
    pf.verdict, pf.verdict_detail = _compute_verdict(pf)
    return pf


def _compute_verdict(pf: PreflightResult) -> tuple[PreflightVerdict, str]:
    """Determine overall preflight verdict from individual check results."""
    reasons: list[str] = []

    # Critical failures → FAILED
    if pf.dns_result and pf.dns_result.status in (TestStatus.FAIL, TestStatus.TIMEOUT):
        if pf.is_block_ip:
            reasons.append(f"DNS block IP ({pf.block_ip_detail})")
        elif pf.dns_result.error_code == "DNS_FAIL":
            reasons.append("DNS resolution failed")
        elif pf.dns_result.error_code == "DNS_TIMEOUT":
            reasons.append("DNS timeout")
        else:
            reasons.append("DNS error")

    # Only HTTP_INJECT is a preflight failure; CONNECT_ERR/TIMEOUT on port 80
    # are expected for HTTPS-only sites and should not fail preflight.
    if pf.http_check and pf.http_check.status == TestStatus.FAIL:
        if pf.http_check.error_code == "HTTP_INJECT":
            reasons.append(f"ISP injection ({pf.http_check.detail})")

    if reasons:
        return PreflightVerdict.FAILED, "; ".join(reasons)

    # Warnings
    warnings: list[str] = []
    if pf.tcp_443 and pf.tcp_443.status != TestStatus.OK:
        warnings.append("TCP :443 unreachable")

    if pf.ping and pf.ping.status != TestStatus.OK:
        warnings.append("ICMP ping failed")

    if warnings:
        return PreflightVerdict.WARNING, "; ".join(warnings)

    return PreflightVerdict.PASSED, "All checks passed"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def run_preflight(
    domains: list[str],
    callback: object | None = None,
    parallel: int = DEFAULT_PARALLEL,
    cancelled: Callable[[], bool] | None = None,
) -> list[PreflightResult]:
    """Run preflight checks for a list of domains.

    Parameters
    ----------
    domains : list[str]
        Domain names to check.
    callback : BlockcheckCallback-like, optional
        Object with ``on_log(msg)`` and ``on_progress(current, total, msg)`` methods.
    parallel : int
        Max concurrent domains.
    cancelled : callable, optional
        Returns True if the run should be aborted.

    Returns
    -------
    list[PreflightResult]
        One result per domain, in the same order as input.
    """
    if not domains:
        return []

    _log = getattr(callback, "on_log", None)
    _progress = getattr(callback, "on_progress", None)

    if _log:
        _log(f"Preflight: checking {len(domains)} domains")

    results: dict[str, PreflightResult] = {}
    total = len(domains)

    workers = min(parallel, total)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_domain = {
            pool.submit(_check_one_domain, domain): domain
            for domain in domains
        }

        for future in as_completed(future_to_domain):
            if cancelled and cancelled():
                pool.shutdown(wait=False, cancel_futures=True)
                break

            domain = future_to_domain[future]
            try:
                pf_result = future.result()
            except Exception as e:
                logger.exception("Preflight failed for %s", domain)
                pf_result = PreflightResult(
                    domain=domain,
                    verdict=PreflightVerdict.WARNING,
                    verdict_detail=f"Preflight error: {e}",
                )

            results[domain] = pf_result
            done = len(results)

            verdict_label = pf_result.verdict.value.upper()
            if _log:
                _log(f"  Preflight {domain}: {verdict_label} — {pf_result.verdict_detail}")
            if _progress:
                _progress(done, total, f"Preflight: {domain}")

    # Return in input order
    ordered = [results.get(d, PreflightResult(domain=d)) for d in domains]

    if _log:
        passed = sum(1 for r in ordered if r.verdict == PreflightVerdict.PASSED)
        warned = sum(1 for r in ordered if r.verdict == PreflightVerdict.WARNING)
        failed = sum(1 for r in ordered if r.verdict == PreflightVerdict.FAILED)
        _log(f"Preflight summary: {passed} passed, {warned} warnings, {failed} failed")

    return ordered
