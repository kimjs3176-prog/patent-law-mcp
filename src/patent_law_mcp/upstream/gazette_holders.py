"""공보 첫 면의 (73) 특허권자 / (71) 출원인 이름 추출기.

포팅 원본: patent-video-skill/scripts/kipris.py (holders_from_text, _ADDR, _CODE)
주소 줄(과 줄바꿈된 주소 꼬리)을 버리고 이름만 남긴다.
"""

import re
from typing import List, Optional, Tuple

_ADDR = re.compile(
    r"(특별시|광역시|특별자치|[가-힣]+도\s|[가-힣]+시\s|[가-힣]+군\s|[가-힣]+구\s|[가-힣\d]+(로|길)\s*\d|번지|\d+-\d+|[가-힣]+(읍|면|동)\s|\b\d{5}\b)"
)
_CODE = re.compile(r"\(\s*(\d{2})\s*\)")


def holders_from_text(txt: str) -> Tuple[List[str], Optional[str]]:
    """(73) 특허권자(등록공보) 또는 (71) 출원인(공개공보) 아래의 이름들. 반환: (이름 목록, "73"|"71"|None)"""
    first = txt.split("=====PAGE=====")[0]
    for kind, label in (("73", r"특\s*허\s*권\s*자"), ("71", r"출\s*원\s*인")):
        m = re.search(rf"\(\s*{kind}\s*\)\s*{label}\s*", first)
        if not m:
            continue
        rest = first[m.end():]
        stop = _CODE.search(rest)  # 다음 INID 코드, 예: (72) 발명자
        block = rest[: stop.start()] if stop else rest[:400]
        names: List[str] = []
        for line in re.split(r"\n+", block):
            line = re.sub(r"\s+", " ", line).strip(" ,;")
            if not line or line[0] in "(（0123456789":  # 줄바꿈된 주소 꼬리나 우편번호
                continue
            cut = _ADDR.search(line + " ")  # 주소 줄, 또는 같은 줄에 주소가 붙은 이름
            line = (line[: cut.start()] if cut else line).strip(" ,;")
            if line and len(line) <= 60 and line not in names:
                names.append(line)
        if names:
            return names, kind
    return [], None
