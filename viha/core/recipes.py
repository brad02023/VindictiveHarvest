from __future__ import annotations

from urllib.parse import quote_plus

from viha.core.models import Seed
from viha.core.handles import recipe_profile_urls
from viha.core.normalize import (
    email_local_part,
    normalize_email,
    normalize_phone,
    phone_search_forms,
    split_usernames,
)


def recipe_links(seed: Seed) -> list[tuple[str, str, str]]:
    """IntelTechniques-style public search URLs. (label, url, section)"""
    name = seed.full_name.strip()
    email = normalize_email(seed.email)
    local = email_local_part(seed.email)
    phone = normalize_phone(seed.phone)
    pretty = phone_search_forms(seed.phone)[2] if len(phone_search_forms(seed.phone)) > 2 else seed.phone
    org = seed.org.strip()
    city = seed.city.strip()
    state = (seed.state or "").strip().upper()
    handles = split_usernames(seed.username)
    qn = quote_plus(name) if name else ""
    out: list[tuple[str, str, str]] = []

    if name:
        extra = f"+{quote_plus(city)}" if city else ""
        out += [
            ("DuckDuckGo name", f"https://duckduckgo.com/?q=%22{qn}%22{extra}", "web"),
            ("Bing name", f"https://www.bing.com/search?q=%22{qn}%22{extra}", "web"),
            ("Google name", f"https://www.google.com/search?q=%22{qn}%22{extra}", "web"),
            ("Instagram people", f"https://www.google.com/search?q=site%3Ainstagram.com+{qn}", "social"),
            ("Facebook people", f"https://www.facebook.com/public/{quote_plus(name.replace(' ', '-'))}", "social"),
            ("Facebook search", f"https://www.google.com/search?q=site%3Afacebook.com+{qn}", "social"),
            ("LinkedIn", f"https://www.google.com/search?q=site%3Alinkedin.com%2Fin+{qn}", "social"),
            ("TikTok", f"https://www.google.com/search?q=site%3Atiktok.com+{qn}", "social"),
            ("X / Twitter", f"https://www.google.com/search?q=site%3Ax.com+{qn}", "social"),
            ("Steam", f"https://steamcommunity.com/search/users/#text={qn}", "social"),
            ("GitHub users", f"https://github.com/search?q={qn}&type=users", "social"),
            ("Reddit", f"https://www.google.com/search?q=site%3Areddit.com+{qn}", "social"),
            ("YouTube", f"https://www.youtube.com/results?search_query={qn}", "social"),
            ("CourtListener opinions", f"https://www.courtlistener.com/?q=%22{qn}%22&type=o", "legal"),
            ("CourtListener dockets", f"https://www.courtlistener.com/?q=%22{qn}%22&type=d", "legal"),
            ("Criminal / court search", f"https://duckduckgo.com/?q=%22{qn}%22+(court+OR+docket+OR+criminal+OR+indictment)", "legal"),
            ("Property / deed / mortgage", f"https://duckduckgo.com/?q=%22{qn}%22+(assessor+OR+appraisal+OR+deed+OR+mortgage+OR+recorder)", "property"),
            ("UCC / lien", f"https://duckduckgo.com/?q=%22{qn}%22+(UCC+OR+lien+OR+%22financing+statement%22)", "property"),
            ("OpenSanctions", f"https://www.opensanctions.org/search/?q={qn}", "sanctions"),
            ("OpenCorporates", f"https://opencorporates.com/officers?q={qn}", "business"),
            ("SEC EDGAR", f"https://efts.sec.gov/LATEST/search-index?q=%22{qn}%22", "business"),
            ("FEC", f"https://www.fec.gov/data/browse-data/?tab=candidates", "legal"),
            ("News", f"https://duckduckgo.com/?q=%22{qn}%22+news", "web"),
            ("Wayback name", f"https://web.archive.org/web/*/{qn}", "web"),
        ]
    if email:
        qe = quote_plus(email)
        out += [
            ("DuckDuckGo email", f"https://duckduckgo.com/?q={qe}", "web"),
            ("Gravatar", f"https://www.gravatar.com/{email}", "identity"),
            ("HIBP (browser)", f"https://haveibeenpwned.com/account/{qe}", "web"),
            ("Epieos-style search", f"https://duckduckgo.com/?q={qe}+(instagram+OR+facebook+OR+github+OR+steam)", "social"),
        ]
    if local:
        ql = quote_plus(local)
        out += [
            ("Username DDG", f"https://duckduckgo.com/?q={ql}", "social"),
            ("WhatsMyName online", f"https://whatsmyname.app/", "social"),
        ]
    if pretty or phone:
        qp = quote_plus(pretty or phone)
        out += [
            ("Phone DDG", f"https://duckduckgo.com/?q={qp}", "web"),
            ("Phone Bing", f"https://www.bing.com/search?q={qp}", "web"),
            ("FCC complaint search", "https://opendata.fcc.gov/browse?category=Consumer-Complaints", "web"),
        ]
        if phone.startswith("+1") and len(phone) == 12:
            dashed = f"{phone[2:5]}-{phone[5:8]}-{phone[8:]}"
            out += [
                ("FastPeopleSearch reverse phone", f"https://www.fastpeoplesearch.com/{dashed}", "identity"),
                ("Intelius reverse phone", f"https://www.intelius.com/reverse-phone-lookup/{dashed}", "identity"),
            ]
    if org:
        qo = quote_plus(org)
        out += [
            ("Org DDG", f"https://duckduckgo.com/?q=%22{qo}%22", "business"),
            ("crt.sh", f"https://crt.sh/?q={qo}", "infra"),
            ("OpenCorporates companies", f"https://opencorporates.com/companies?q={qo}", "business"),
        ]
    for handle in handles:
        qh = quote_plus(handle)
        out.append((f'DuckDuckGo "{handle}"', f"https://duckduckgo.com/?q=%22{qh}%22", "social"))
        for label, url in recipe_profile_urls(handle):
            out.append((label, url, "social"))
    st = state or ("TX" if (phone or "").startswith("+1210") or (seed.phone or "").replace(" ", "").startswith("210") else "")
    if st == "TX" or (state == "TX"):
        out += [
            ("TX SOS entity search", "https://www.sos.state.tx.us/corp/sosda/index.shtml", "business"),
            ("TX Comptroller taxpayer", "https://mycpa.cpa.state.tx.us/coa/", "business"),
            ("Bexar CAD (210)", "https://bexar.trueautomation.com/clientdb/?cid=110", "property"),
            ("Guadalupe CAD (210 metro)", "https://propaccess.trueautomation.com/clientdb/?cid=75", "property"),
            ("Guadalupe CAD eSearch", "https://esearch.guadalupecad.org/", "property"),
            ("TX UCC (SOSDirect)", "https://direct.sos.state.tx.us/", "property"),
            ("TX courts search", "https://www.txcourts.gov/", "legal"),
            ("TX license search", "https://www.tdlr.texas.gov/LicenseSearch/", "business"),
        ]
    if (city or state) and name:
        place = quote_plus(" ".join(p for p in (city, state) if p))
        out.append(
            (
                "Property / assessor search",
                f"https://duckduckgo.com/?q=%22{qn}%22+{place}+(assessor+OR+appraisal+OR+deed+OR+mortgage)",
                "property",
            )
        )
    return out


def reverse_image_links(image_url_or_hint: str) -> list[tuple[str, str]]:
    q = quote_plus(image_url_or_hint)
    return [
        ("Yandex reverse image", f"https://yandex.com/images/search?rpt=imageview&url={q}"),
        ("Google Lens URL", f"https://lens.google.com/uploadbyurl?url={q}"),
        ("TinEye", f"https://tineye.com/search?url={q}"),
        ("Bing visual", f"https://www.bing.com/images/search?q=imgurl:{q}&view=detailv2&iss=sbi"),
    ]
