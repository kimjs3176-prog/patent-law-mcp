# 특허 기술소개영상 콘텐츠 작성 규칙 (content JSON)

각 특허마다 `data/content/<order 3자리>-<appno>.json` 1개를 작성한다. 생성기(`tools/build.py`)가 이 JSON으로
60초 언팩(신제품 발표회) 스타일 영상을 만든다. 예시(프로젝트의 `tools/examples/`, 스킬 폴더에서는 `references/examples/`): `007-1020190166418.json`(장치형, anatomy),
`137-1020190145266.json`(공정+수치형, stats), `146-1020210079188.json`(바이오 소재형, stats).
**작성 전에 예시 3개를 반드시 읽는다.**

## 입력
- `data/master.json`: order, appno, title, status
- `data/patents/<appno>/biblio.json`: 서지·요약·청구항(등록 청구항 = 권리범위, 가장 신뢰), rnd(과제정보)
- `data/patents/<appno>/fulltext.txt`: 공보 전문(발명의 효과·실시예·표). 공개공보일 수 있으니 청구항은 biblio.json 우선
- `data/patents/<appno>/fig-*.jpg / fig-*.png`: 도면 이미지(png = 흑백 기계도면, 부호 확인에 적합) (anatomy용, 필요할 때만 Read로 확인)

## 절대 규칙 (사실성)
1. 모든 수치·조건·효과는 명세서/청구항에 적힌 그대로. 계산해서 새 주장을 만들지 않는다(예: 23.6→14.6을 "38% 감소"로 쓰지 않음, "N배"는 명세서에 그 표현이 있을 때만).
2. 명세서에 없는 효과·시장·매출·인증은 쓰지 않는다. 활용분야(apps)는 청구항·발명의 효과·명세서에 언급된 용도 위주, 필요시 그 용도의 자연스러운 적용처까지만.
3. 청구항에 직접 포함된 용도는 apps 항목에 `"claim": true` (최대 3개).
4. 수치 데이터가 없는 특허(장치·시스템 등)는 proof.kind = "anatomy"로 하고, 구성요소 번호가 보이는 도면(사시도 등)을 figure로 지정. 부품 순서를 도면 부호 순서와 맞추고 source에 "(부호는 도면 번호와 동일)"을 적되, 실제로 일치할 때만.
   각 부품에 `x`·`y`(그 도면 이미지의 가로·세로 비율 0~1)를 넣으면 모든 템플릿의 구성 장면에서 **도면 위 그 부품 자리에 부호 표식**이
   목록과 같은 순서로 나타난다. 도면을 Read로 직접 열어, 부호의 지시선을 따라간 끝 **부품 위**(부호 글자가 아니라)를 찍는다.
   확신이 없는 부품은 x·y를 빼면 표식만 생략된다(틀린 표식보다 낫다). 시그니처 loop의 callouts와 같은 도면이면 같은 좌표를 쓴다.
   블록도·순서도처럼 상자 안에 글자가 있는 도면은 상자 오른쪽 위 모서리 안쪽에 찍어 글자를 가리지 않게 한다.
   찍는 방법은 `references/FIGURE_ANALYSIS.md`(스킬) — `python -I tools/figmap.py <파일>`이 부호 대조표와 10×10 격자 도면을 만들어 준다.
   흑백 선 도면은 빌드 때 선이 자동 추출되어 그려지므로(`figtrace.py`), 구성 장면에는 부호가 잘 보이는 **선 도면**을 고르는 편이 좋다.
5. 수치 데이터가 있으면 proof.kind = "stats", items 1~3개. 대조군 대비 막대(bars)는 표에 있는 값만. 그래프만 있고 수치가 본문에 없으면 그 막대는 넣지 않는다.
6. 명세서 내부 모순(단위 오기 등)이 있으면 더 타당한 쪽을 쓰고 `"notes"` 필드에 한 줄 기록.

## 문체
- 한국어 개조식. 문장형 종결("~합니다") 금지. 짧게.
- 글자 수 한도(넘으면 화면에서 잘림):
  - name: 영문 대문자 코드네임 2단어, 공백 포함 14자 이내, 뒤 단어 앞에 `|`(그라디언트 구분). 예 `"DEW |POT"`, `"POP RICE |BREW"`
  - sub: 한글 20자 이내 (기술 한 줄 설명)
  - headline, process.title, features.title, proof.title: 22자 이내, 강조할 끝부분 앞에 `|`
  - chips[].k 12자, chips[].v+u 10자(한글은 8자) 이내
  - process.steps[].n 9자, d 18자, big+u 8자(한글이면 4자) — big은 그 단계의 핵심 수치(조건) 또는 영문 동사 1단어(SENSE, COOL…)
  - process.note 40자 이내
  - proof.items[].big+u 8자, l 12자, s 2줄(`<br />`로 구분, 줄당 18자)
  - bars[].l 14자, bars[].t 8자
  - anatomy parts[].n 10자, d 22자 (최대 6개)
  - features.big.l 12자, big.s 14자; tiles[] 6개: v 7자(한글 5자), l 9자, s 13자
  - apps[] 5개: n 8자, s 2줄(`<br />`, 줄당 9자)
  - source 50자 이내: "자료: 등록특허 제10-XXXXXXX호 명세서 (표/도/실시예)"
- 등록특허면 `"patlabel": "등록특허"`, regno = 등록번호(10-XXXXXXX, 뒤 -0000 제거). 공개특허(미등록)면 `"patlabel": "공개특허"`, regno = 공개번호.
- institute: 전문의 "주관기관" 또는 "과제수행기관명"(또는 rnd)에 국립○○원이 있으면 "농촌진흥청 국립○○원", 없으면 "농촌진흥청".

## 디자인 필드
- palette: amber(식품·발효·곡물), green(작물·재배·친환경·토양), violet(바이오·기능성·화장품), aqua(장치·물·스마트팜·센서), rose(축산·반려동물·건강), blue(미생물·의약·분석·소프트웨어) 중 택1
- hero, apps[].icon, proof.items[].icon: 아래 이름 중에서만
  beer rice flask leaf sprout cell dna pot drop snow chip fan shield bowl globe capsule bottle factory cup chart thermo gear spark home hand coins pin fork animal tractor sun seed fish box water sensor mushroom bee

## 스키마
```json
{
  "order": 7, "appno": "1020190166418", "regno": "10-2387406", "patlabel": "등록특허",
  "title": "발명의 명칭 원문", "name": "DEW |POT", "sub": "...", "institute": "...",
  "palette": "aqua", "hero": "pot", "headline": "앞부분 |강조",
  "chips": [{"k": "", "v": "", "u": ""}, x4],
  "process": {"title": "", "steps": [{"n": "", "d": "", "big": "", "u": ""}, 3~6개], "note": ""},
  "proof": {"kind": "stats", "eyebrow": "PERFORMANCE",
            "items": [{"big": "", "u": "", "l": "", "s": "", "bars": [{"l": "", "v": 0, "t": "", "hi": true}], "max": 0, "icon": "shield"}]}
     또는 {"kind": "anatomy", "eyebrow": "ANATOMY", "title": "", "figure": "fig-p8-IM6.jpg", "figcap": "", "parts": [{"n": "", "d": "", "ref": "도면 부호(있을 때만, 예: 110)", "x": 0.42, "y": 0.35}]},
  "source": "",
  "features": {"title": "", "big": {"l": "", "s": ""}, "tiles": [{"v": "", "l": "", "s": ""}, x6]},
  "apps": [{"icon": "", "n": "", "s": "줄1<br />줄2", "claim": true}, x5],
  "notes": "선택: 명세서 모순·판단 근거",
  "narration": {"hook": "", "overview": "", "process": "", "proof": "", "figures": "", "features": "", "apps": "", "outro": ""},
  "branding": {"contact": "", "contact_label": "", "holder": "", "holder_label": "", "disclaimer": ""}
}
```
- branding(선택): 이 특허만 엔딩 문구를 바꿀 때. 쓴 키만 적용되고 나머지는 프로젝트 `branding.json` → 스킬 기본값을 따른다.
  특허권자는 공보의 (73) 특허권자 / (71) 출원인에서 자동으로 들어가므로 보통 쓰지 않는다. 공보에서 잘못 읽혔을 때만 `holder`를 쓴다
  (`{institute}`는 `institute`로 바뀜, 빈 문자열 `""`은 그 줄을 비움). 문의처·면책이 모두 같다면 `branding.json`만 고친다.
- bars: 하이라이트(이 기술) 항목에 `"hi": true`, max는 막대 최대값보다 약간 크게. bars가 없으면 item에 icon 지정.
- stats item은 각 4초 이상 보이므로 1~3개.
- `process.steps[].big`은 **명세서의 측정값**(온도·시간·비율 등 숫자)만. 수치가 없는 단계는 `""`로 둔다(MIX·DRY 같은 영단어 금지 —
  빌드 때 숫자가 없는 값은 자동으로 숨겨진다). 온도 단계는 `u`를 `°C`로, 범위는 `160–200`처럼 쓰면
  A·D 템플릿이 그 특허의 온도 프로파일(단계별 범위 띠와 이어지는 선)을 공정 장면에 그린다(온도 단계 2개 이상일 때).
- 단계 그림은 단계 이름의 키워드로 고른다(`visuals.STEP_ICONS`). 맞는 키워드가 없으면 단계 설명(`d`)의 키워드, 그다음 특허의 대표 아이콘(`hero`)이 나오므로(화살표 자리채움 없음),
  단계 이름은 "가열·건조·발효·센서 측정"처럼 동작이 드러나게 쓴다.
  특장점 큰 카드(`features.big`)는 키워드가 없으면 화살표 대신 특허의 대표 아이콘(`hero`)을 쓴다.

## 나레이션 대본 (narration, 권장 — 모든 렌더링에 기본으로 들어감, 끄려면 `--no-narrate`)
화면 글자(개조식)를 그대로 읽지 말고, 같은 사실을 **말하는 문장**으로 쓴다. 장면마다 1~2문장.
엔딩(outro)은 항상 음성 없이 음악만 — `outro`를 써도 읽지 않는다. 음성은 Google Chirp 3 HD(키가 있을 때) 또는 선희(ko-KR-SunHiNeural). 화면용 기호는 합성 직전에 읽는 말로 바뀌지만(`~`→"에서", `℃`→"도", `·`→쉼표), 대본은 처음부터 말로 쓴다.
- 음절 한도(공백 제외): hook 30 · overview 30 · process 45 · proof 50 · figures 25 · features 30 · apps 30 · outro 25.
  넘치면 템플릿별로 빨리 읽히거나 뒤 문장부터 잘리므로, **문장 하나만 남아도 말이 되게** 핵심을 앞 문장에 둔다.
- 수치는 명세서 그대로, 읽기 쉽게: `0.6–1.1 MPa` → "0.6에서 1.1 메가파스칼", `%` → "퍼센트", `℃` → "도". 계산한 배수 금지.
- figures: 실제 도면 종류를 확인했을 때만 구체적으로("공정도와 사진"), 아니면 "명세서 도면으로 구조를 살펴봅니다." 정도.
- outro: 읽지 않는다(엔딩은 음악만). 면책 문구도 읽지 않는다(화면 표기).
- 기관명·코드네임은 화면에 있으므로 반복하지 않아도 된다. 과장·광고성 표현("획기적", "최고") 금지.
- **자연스러운 말투**(방송 내레이션처럼):
  - 이어 주는 말로 흐름을 만든다: "먼저", "~한 다음", "마지막으로", "그 결과", "덕분에".
  - 한 문장에 숫자는 하나~둘. 단계·조건을 쉼표로 나열하지 않는다(나열은 화면이 보여 준다).
  - 소수 둘째 자리는 꼭 필요할 때만("78.03그램" → "78그램", 화면에는 원래 값). 단, 비교 기준이 되는 값은 그대로.
  - 쉼표는 숨 쉴 자리에만 넣는다(TTS가 쉼표에서 쉰다). "~입니다"만 반복하지 말고 "~합니다", "~했습니다"를 섞는다.
  - 주어를 사람·재료로 세우고 동사로 끝낸다: ✗ "당화, 60에서 80도." ○ "맥아와 함께 따뜻한 물에서 당화합니다."
  - 한자어 명사 나열(“~화”, “~성”, “~적”)보다 풀어 쓴 말: ✗ "공정 단순화 및 수율 향상" ○ "공정은 짧아지고, 얻는 양은 늘어납니다."
  - 한 문장은 소리 내어 한숨에 읽히는 길이(공백 제외 25음절 안팎). 길면 두 문장으로 나눈다.
  - 장면이 바뀌어도 이야기는 이어지게: 앞 장면의 끝말을 받아 시작한다("그 결과", "이렇게 만든", "덕분에").
  - 쓴 뒤 소리 내어 읽어 본다. 화면 글자를 읽는 것처럼 들리면 다시 쓴다.
  - 예) ✗ "감자를 썰어 전분을 씻고, 식초 물에 80에서 100도로 데칩니다. 말린 뒤 한 번 튀기고, 영하 60도 아래로 급속 냉각한 다음 다시 튀겨 완성합니다."
    ○ "먼저 감자를 썰어 물에 담가 전분을 빼고, 식초를 푼 물에 살짝 데칩니다. 물기를 말려 한 번 튀긴 다음, 아주 차갑게 급속 냉각하고, 마지막으로 한 번 더 튀겨내면 완성입니다."
- 음성은 보통 속도(+0%)로 먼저 읽히고, 장면에 안 들어갈 때만 +6·+12·+18%로 빨라진다. 장면 길이(초) × 약 6음절을 넘기지 않으면 보통 속도로 들어간다.
- 없으면 내용 필드로 단순 대본을 자동 생성한다(품질 낮음 → 대량 제작 때도 작성 권장).

## 특징 구조화 (시그니처 설계 — 콘텐츠보다 먼저)
목표는 **특허마다 다른 영상**이다. 템플릿이 같아도 화면에서 움직이는 것은 "그 기술이 실제로 움직이는 것"이어야 한다.
문구를 쓰기 전에 명세서·청구항·도면으로 그 기술의 구조를 먼저 뽑는다.
1. **한 문장 요약**: "이 기술은 [무엇]을 [어떻게] 해서 [무엇이 된다 / 무엇을 찾는다 / 어떻게 돈다]."
2. **다섯 질문** (답이 곧 signature 데이터다):
   | 질문 | 답이 들어가는 곳 |
   |---|---|
   | 무엇이 **바뀌나** (재료의 형태·상태) | journey `stages[].key`·`cond` |
   | 무엇이 **흐르나** (공기·물·가스·빛·고형물·전력) | loop `run.flows[]`(매질 `color` + 도면 위 실제 경로 `pts`) |
   | 무엇을 **알아보나** (서열·표적·신호) | sequence `primers`·`layout`·`result` |
   | 기존과 **무엇이 다른가** (빠진 단계, 더해진 제어, 프로브) | `conventional`/`removed` · `run.logic`+`rules` · `probe` |
   | 결과를 **무엇으로 보이나** (온도 조건·판독 방식·실측 수치) | `stages[].t` · `result.kind`(ct/tubes/gel) |
3. **유형 고르기**:
   | 특허 | type | 움직이는 것 |
   |---|---|---|
   | 식품·가공·추출·발효 공정 | journey | 재료가 단계마다 모양을 바꾸며 온도 그래프를 따라간다 |
   | 장치·설비·재배 시스템·센서 | loop | 도면 위로 매질이 실제 경로를 흐르고, 제어 루프나 단계가 돈다 |
   | 프라이머·마커·진단 키트 | sequence | 실제 염기가 찍히고 표적 부위가 켜진 뒤, 명세서의 판독 방식으로 결과가 나온다 |
   | 미생물·균주 | 배양·발효 공정이 핵심이면 journey, 진단 마커가 있으면 sequence, **분리·선발된 균주 자체**가 핵심이면 lineage | 분리원 → 선발 단계 → 균주, 대조 균주와 활성 비교 |
   | 조성물·배합 | 제조 공정이 핵심이면 journey(mix·heat·dry …), **배합 비율과 효능**이 핵심이면 formula | 성분이 비율대로 채워지고, 효능이 대조군 대비 막대로 |
   | SW·제어 시스템 | 구성도가 있으면 loop(데이터·전력 흐름 `power`/`light`, 청구항 제어 루프) | |
   | 품종·육종(분자마커 없음) | **lineage** | 교배 부모(또는 분리원) → 세대·선발 단계 → 신품종, 형질이 대비 품종과 나란히 |
   | 다른 유형이 맞지 않으면 | **claim** — 모든 특허에 쓸 수 있는 범용 유형 (항원·화합물·용도 발명, 공정·장치·서열·배합·계보가 없는 특허) | 독립항이 구성요소별로 조립되며 도면 위 표식(또는 구성 블록)과 이어지고, 특징부가 빛난 뒤 종속항이 가지로 자란다 |
4. **차별화 규칙**:
   - 단계 그림(`key`)은 재료가 실제로 겪는 변화로 고른다. 같은 그림이 이어지면 조건 차이(온도·시간)를 `cond`·`t`로 보이게 한다.
   - 도면 좌표·경로는 도면을 직접 열어 찍는다(추정 금지). 경로는 매질이 지나는 순서대로.
   - 온도·서열·밴드 크기·Ct는 명세서 값 그대로. 없으면 `label`로 시간·비율 등 다른 핵심 조건을 쓴다.
   - 그림이 안 맞으면 대표 아이콘으로 때우지 말고 뺀다.
   - 여러 건을 만들면 `python -I tools/sigcheck.py data/content/*.json`을 돌린다. **구조 오류 0건**이어야 하고,
     "같은 구성으로 보일 수 있음" 경고가 나온 묶음은 그 특허만의 요소(단계 그림·매질·판독·두 번째 도면·공정 편집) 하나 이상을 바꾼다.
     claim끼리는 도면 표식·특징부 구성·인용 관계·실시예 수치로 갈린다.
5. **나레이션도 같은 구조로**: 재료 여정은 변화 순서대로, 장치는 매질이 지나는 순서대로, 서열은 문제 → 인식 → 판독 순서로,
   청구항은 구성 → 특징부 → 종속항(→ 실시예 수치) 순서로 말한다.

## 시그니처 장면 (signature — 템플릿 S, 특허마다 다른 영상의 핵심)
기술 자체가 움직이는 장면. `type`에 따라 이야기 순서와 핵심 장면이 바뀐다. **모든 값은 명세서·청구항·도면에서 확인한 것만.**
도면 위 위치(x, y)는 그 도면 이미지의 가로·세로 비율(0~1)로, 도면을 직접 보고 부호가 가리키는 부품 위에 찍는다.

- `journey` (식품·공정): `product` · `title`("쌀이 |쌀맥주가 되기까지" 형식, 생략 시 자동) ·
  `stages[{n, key, cond, t:[최저,최고]℃ 또는 label}]` 4~6개(온도는 음수 가능, 축 범위는 자동). 온도가 2단계 미만이면 온도 그래프 대신 단계 레일과 각 단계의 label(시간·비율 등)로 보여 주므로, 온도가 없는 공정도 journey로 쓴다.
  key(그림): soak(침지·당침) · cut(절단) · steam(증숙) · heat(가열·데침·효소처리) · boil(끓임+홉) · dry(건조) · roast(로스팅) ·
  fry(유탕) · freeze(동결·냉각) · ferment(발효) · mix(혼합·배합) · extract/filter(추출·여과·농축) · puff(팽화) · mash(당화) ·
  cold(저온 숙성 → 완제품 잔) · mill(분쇄·제분·도정) · form(성형·분할·고형화·겔화) · inoculate(접종) · sterilize(살균·멸균) ·
  coat(코팅·분무·도포) · pack(포장·충진·실링) · concentrate(농축·증발) · harvest(수확·채취) · extrude(압출) ·
  bake(굽기) · sprout(발아) · grow(재배·생육) · wash(세척·박피) · char(탄화·열분해) · thaw(해동) · light(광 조사·LED) · sonicate(초음파). 없으면 단계 이름으로 아이콘을 고른다.
  선택: 명세서가 기존 공정의 한 단계를 없앤다고 **명시**할 때만 `conventional` · `removed` · `removed_note` · `route_note` · `route_label`
  (공정 비교 장면이 추가되고, 없으면 강점 장면이 들어간다).
- `loop` (장치): `figure` · `figcap` · `parts_title`(선택) · `callouts[{ref, n, d, x, y}]` 3~5개 ·
  `run{figure?, eyebrow, title, flows[{label, color, pts}], glows[{x, y | ref | at_flow, color}], logic+rules 또는 steps[{n, d}], drip?}` ·
  `path{figure, figcap, eyebrow, title, color, points[{ref, n, d, x, y}]}`(선택, 두 번째 도면 위 이동 경로).
  color: air · water · heat · cold · gas · uv · light · solid · power. `logic`(4단계 제어 루프)은 청구항에 센서→제어→구동이 있을 때만, 아니면 `steps`.
  색의 뜻: `power`는 **전기·데이터 신호**(SW·제어 시스템의 데이터 흐름도 이것), `light`는 **실제 빛**(LED·자외선 외 광원, 분광), `uv`는 자외선.
  선택 키: `source`(근거 표기), `flows[].legend: false`(같은 이름 흐름을 범례에 한 번만), `run.drip` `[x, y]` + `drip_label`(응축수처럼 맺혀 떨어지는 방울),
  `glows[]`는 `x, y` 대신 `ref`(그 부호의 callout 자리)나 `at_flow`(0부터 센 흐름 번호, 그 흐름의 두 번째 점)로 자리를 줄 수 있다.
  `path.points[].ref`는 도면 부호 대신 순서도 단계 번호(S210 등)도 된다.
- `formula` (조성물·추출물·기능성 소재): `mix_title`(선택) · `components[{n, v, u?, role?}]` 2~6개(v = 명세서의 비율·함량 숫자, 상대 크기로 용기를 채움) ·
  `base_note`(비율 근거) · `effects[{l, control, treated, unit?, better: "up"|"down", note?}]` 1~4개(대조군·처리군 값은 명세서 그대로, 배수·감소율을 새로 계산하지 않음) ·
  `effects_title` · `effects_note`(자료 출처) · `control_label`/`treated_label`(선택, 기본 대조군/처리군). 장면: teaser · mix · effect · features · apps.
- `lineage` (품종·선발 균주): `variety`(신품종·균주 이름) · `cross{mother, father}`(교배) 또는 `source`(분리원·선발 모집단) ·
  `steps[{gen, l, year?}]` 3~6개(F1·F2~F5·생산력 검정·지역 적응·품종 등록 / 분리·스크리닝·동정 …, 마지막이 신품종) · `tree_title`(선택) ·
  `check`(대비 품종·대조 균주) · `traits[{l, new, check, unit?, better}]` 1~5개(명세서 특성 조사표 값 그대로) · `traits_title` · `traits_note`.
  장면: teaser · tree · traits · features · apps.
- `sequence` (프라이머·진단): `problem{title, cards[{v, l, s}] 2~3개, src}` · `target` · `target_note` · `layout`(표적 부위 순서) ·
  `primers[{id, seq, regions}]`(서열번호의 실제 염기, 8개 이하) · `primers_title`/`primers_cap`(선택) · `field`(칩 2~4개) ·
  `result` 중 하나: `{kind: "tubes", tubes[{l, pos}], pos_color, neg_color, note, cap}`(육안 색 판독) ·
  `{kind: "gel", ladder[bp], lanes[{l, bands[bp]}], note, cap}`(전기영동) ·
  `{kind: "ct", sensitivity/specificity[{l, ct}], *_title, *_note}` + 최상위 `cycles` · `cutoff`(실시간 PCR).
  선택: `probe{seq, dye, sybr_pos{l, ct}, sybr_ntc[], pos[{l, ct}], ntc_n, left_title, right_title}`(프로브 비교 장면).
- `claim` (범용 — 다른 유형이 맞지 않는 모든 특허): 독립항의 구조 자체를 움직인다. **값은 등록 청구범위(biblio.json `claims`)가 먼저**, 없으면 공보 청구범위.
  `claim{no, preamble, elements[{n, d, ref?, x?, y?}], feature{idx, l}}` — `preamble`은 전제부(청구 대상, 짧게: "항원 단백질"),
  `elements` 3~5개는 독립항의 구성요소 순서대로(`ref`는 도면 부호가 있을 때, 없으면 순번이 표식이 됨),
  `feature.idx`는 특징부("~을 특징으로 하는" 부분, 신규한 구성)인 elements 번호(0부터, **일부만** — 나머지가 물러나야 특징부가 보임), `feature.l`은 특징부 한 줄 요약 ·
  `figure`(선택, 구성요소를 짚을 도면 하나) + `figcap` — 도면이 있으면 x·y가 있는 구성요소마다 도면 위 표식과 선으로 이어지고(x·y는 figmap 격자로 측정, 도면에 없는 구성요소는 x·y 없이),
  도면이 없으면 청구 대상의 틀 안에 구성 블록이 조립된다(화면에 "모식" 표기) ·
  `deps[{no, l, of?}]` 2~5개(종속항·인용항, 청구항 번호 순; `of`는 독립항이 아닌 앞의 항을 인용할 때 그 번호 또는 목록 — 그 행에서 가지가 나옴, 묶을 때 `no`는 "3·4"도 됨) ·
  `evidence{l, control, treated, u?, better, control_label?, treated_label?, src?}`(선택, 실시예의 대표 수치 하나 — 값 그대로, 새로 계산하지 않음) ·
  선택 제목: `anatomy_title`(기본 "청구항 N의 |구성") · `tree_title`(기본 "<전제부>의 |권리 범위") · `tree_note`(기본 "등록 청구범위 · 종속항은 요약").
  장면: teaser · anatomy · tree · features · apps.
- **개수·글자 한도**(넘으면 validate/sigcheck 오류 또는 화면 잘림):
  | 항목 | 개수 | 글자(한글 기준) |
  |---|---|---|
  | journey `stages` | 4~6 | `n` 10 · `cond` 24 · `label` 12 |
  | loop `callouts` | 3~5 | `n` 10 · `d` 22 |
  | loop `run.flows` / `pts` | 1~3 / 3~6점 | `label` 8 |
  | loop `run.steps` | 3~5 | `n` 9 · `d` 18 |
  | loop `run.logic` / `rules` | 4 / 1~2 | 노드 8 · 규칙 22 |
  | loop `path.points` | 3~5 | `n` 12 · `d` 22 |
  | sequence `problem.cards` · `primers` · `field` | 2~3 · ≤8 · 2~4 | 카드 `l` 14 · `s` 20 |
  | formula `components` / `effects` | 2~6 / 1~4 | 성분 `n` 14 · `role` 18 · 효능 `l` 10 · `note` 12 |
  | lineage `steps` / `traits` | 3~6 / 1~5 | `gen` 8 · `l` 14 · 형질 `l` 10 · 품종명 10 |
  | claim `elements` / `deps` | 3~5 / 2~5 | `preamble` 14 · 구성 `n` 10 · `d` 20 · `feature.l` 24 · 종속 `l` 16 · `evidence.l` 12 · 라벨 10 · `src` 16 |
  | `title`·`parts_title`·`run.title`·`path.title` | — | `|`로 두 덩이, 합쳐 22 이내(`|` 뒤가 강조색) |
- **장면과 길이**(나레이션 키 = 장면, 6초 × 약 6음절 = 28음절 식으로 쓴다. 엔딩은 읽지 않음):
  - journey: teaser 6 · (route 7.5, 공정 편집이 있을 때) · journey 2.6+2.7×단계 수(최소 14) · proof 12 · (features 7, 공정 편집이 없을 때) · apps 6.5
  - loop: teaser 6 · parts 2.4+1.5×부품 수(최소 8) · run 13 · (path 8.5, 있을 때) · features 7 · apps 6.5 — **proof 장면은 없다**(써도 읽히지 않음)
  - formula: teaser 6 · mix 2.8+1.7×성분 수(9~13) · effect 3+1.8×효능 수(8.5~12) · features 7 · apps 6.5
  - lineage: teaser 6 · tree 3.2+1.6×단계 수(9~13) · traits 3+1.6×형질 수(8.5~12) · features 7 · apps 6.5
  - claim: teaser 6 · anatomy 3+1.8×구성 수(9~13) · tree 3+1.4×종속항 수(+1.6, evidence가 있을 때; 8~12) · features 7 · apps 6.5 (전체 41~47초)
  - sequence: teaser 6 · problem 6 · primers 2.6+1.9×프라이머 수(12~16) · (probe 9, 있을 때) · result 9.5 / tubes 8.5 / gel 9.5 · (features 7, 프로브가 없을 때) · apps 6.5
- `narration`(시그니처 안, 권장): 장면별 한 줄 대본. 키는 위 장면 이름(teaser · route/journey · parts/run/path · problem/primers/probe/result/tubes/gel · mix/effect · tree/traits · anatomy/tree(claim) ·
  proof · features · apps 중 그 영상에 있는 것). 장면 길이(초) × 약 6음절 이내(예: journey 18.8초 → 100음절, teaser 6초 → 28음절).
  6음절은 상한이다. 표지(teaser)·짧은 장면은 5음절 안쪽으로 쓰고, `python -I tools/narration.py --check <파일>`로 확인한다.
  숫자·단위는 읽히는 대로(“100에서 105도”, “퍼센트”). 없으면 시그니처 데이터로 자동 대본.
- 모식도인 부분(부위 배치, 물방울 경로)은 화면에 "모식"이라고 표기된다. 곡선은 Ct 값에서 문턱선을 지나도록 그린다.

## 배경음악 (music, 선택 — 키 없이 그 특허만의 곡)
그 기술에 맞는 곡을 직접 설계한다. 쓰면 `compose.py`가 연주해 그 특허의 배경음악으로 쓰고, 안 쓰면 기본 4곡을 돌려 쓴다.
```json
"music": {"mood": "green-field", "bpm": 112, "key": "G", "progression": ["G", "C", "Em", "D"],
          "keys": "piano", "arp": "guitar", "pad": "strings", "lead": "celesta", "perc": "light", "seed": 11}
```
- mood(출발 프리셋): bright-tech(기기·IT) · green-field(재배·농업) · clean-lab(바이오·진단) · warm-craft(식품·가공). 나머지는 덮어쓸 것만.
- progression: 마디당 화음 하나(`chord_bars`로 2마디씩), 반복. 쓸 수 있는 화음: 장3·m·7·maj7·m7·m9·maj9·9·6·m6·sus2·sus4·add9·madd9·dim·aug·7sus4, 분수화음 `A/C#`.
  key만 주면 프리셋 진행을 그 조로 옮긴다. **밝고 경쾌하게**: 장조의 기본 3화음으로 된 팝 진행(I–V–vi–IV, I–IV–vi–V, I–V–IV–V)을 쓴다.
  maj7·m9 같은 재즈 화음이나 단조로 시작하는 진행은 무겁고 심오하게 들리므로 쓰지 않는다.
- keys / arp / lead: epiano · piano · marimba · guitar · celesta · none. pad: pad · strings · none. perc: none · light · pulse. bpm 70~160(기본 112~128, 경쾌하게).
- 나레이션이 주인공이다: lead는 높은 음역에서 드물게만 나오고, 곡 전체가 말소리 대역을 비워 둔다. seed를 바꾸면 같은 설계로 다른 리듬이 나온다.

## 작성 후 자체 점검
- JSON 문법 유효(`python -I -c "import json;json.load(open(path,encoding='utf-8'))"`)
- 모든 수치를 명세서에서 다시 찾아 확인
- 글자 수 한도 확인
