"""Orchestra Zapret2 user presets page.

Dedicated namespace wrapper so orchestra-specific routing does not point to the
direct user-presets module as its canonical entrypoint.
"""

from ui.pages.zapret2.user_presets_page import Zapret2UserPresetsPage


class OrchestraZapret2UserPresetsPage(Zapret2UserPresetsPage):
    def _is_orchestra_backend(self) -> bool:
        return True
