#let build_date = sys.inputs.at("build_date", default: "unknown")
#let korean = "한글 연구 기록과 Inter italic glyphs"
#let mixed = "Appendard 0123456789 ffi office E. coli Drosophila melanogaster"
#let weights = (
  ("Thin", 100),
  ("ExtraLight", 200),
  ("Light", 300),
  ("Regular", 400),
  ("Medium", 500),
  ("SemiBold", 600),
  ("Bold", 700),
  ("ExtraBold", 800),
  ("Black", 900),
)

#set document(title: "SNU Appendard Specimen")
#set page(paper: "a4", margin: 18mm)
#set text(size: 10pt, lang: "en")

#let section(title) = {
  text(size: 18pt, weight: 700)[#title]
  v(8pt)
}

#let small_label(body) = text(size: 8pt, fill: rgb("#555555"))[#body]

#align(center + horizon)[
  #text(font: "SNU Appendard", size: 38pt, weight: 700)[SNU Appendard]
  #v(10pt)
  #text(size: 14pt)[Pretendard-derived OTF family with Inter v4.1 italics]
  #v(18pt)
  #text(size: 10pt)[Build date: #build_date]
  #v(4pt)
  #text(size: 10pt)[OTF/CFF output at UPM 1000]
]

#pagebreak()
#section[Weight Grid: Pretendard]
#table(
  columns: (28mm, 1fr, 1fr),
  inset: 5pt,
  stroke: rgb("#dddddd"),
  [Weight], [Upright], [Synthetic italic],
  ..weights.map(((name, value)) => (
    [#name],
    text(font: "Pretendard", weight: value, size: 13pt)[#korean],
    text(font: "Pretendard", weight: value, style: "italic", size: 13pt)[#mixed],
  )).flatten(),
)

#pagebreak()
#section[SNU Appendard]
#table(
  columns: (28mm, 1fr, 1fr),
  inset: 5pt,
  stroke: rgb("#dddddd"),
  [Weight], [Upright], [Italic],
  ..weights.map(((name, value)) => (
    [#name],
    text(font: "SNU Appendard", weight: value, size: 13pt)[#korean],
    text(font: "SNU Appendard", weight: value, style: "italic", size: 13pt)[#mixed],
  )).flatten(),
)

#pagebreak()
#section[Body Text]
#let body_text(font-name, size) = text(font: font-name, size: size)[
  한글 연구 문서는 Korean text and #emph[English terminology]를 한 문단 안에서
  자연스럽게 섞어 쓴다. Appendard keeps Hangul upright while adding real
  #emph[italic forms] for Latin emphasis in scholarly prose. Figures
  0123456789, punctuation, brackets (A/B), and #emph[common words] should keep
  stable spacing.
]

#for sample in (("10 pt", 10pt), ("11 pt", 11pt), ("12 pt", 12pt)) [
  #let label_text = sample.at(0)
  #let size = sample.at(1)
  #small_label[#label_text]
  #v(3pt)
  #small_label[Pretendard (synthetic italic)]
  #v(2pt)
  #body_text("Pretendard", size)
  #v(4pt)
  #small_label[SNU Appendard (Inter italic)]
  #v(2pt)
  #body_text("SNU Appendard", size)
  #v(10pt)
]

#pagebreak()
#section[Italic Showcase]
#let italic_diagnostics = [
  Diagnostic forms: #emph[a] #emph[f] #emph[j] #emph[g] #emph[y] —
  #emph[affinity], #emph[fjord], #emph[agility], #emph[joyful], #emph[typography].

  In an oblique, letters such as #emph[a], #emph[f], and #emph[j] are usually
  slanted versions of upright forms; true italics change their structure.
]

#columns(2, gutter: 12mm)[
  #small_label[Pretendard (synthetic oblique)]
  #v(4pt)
  #text(font: "Pretendard", size: 11pt)[
    #italic_diagnostics

    Bibliography: Kim, J. (2026). #emph[Mixed-script typography].

    Scientific names: #emph[E. coli], #emph[Drosophila melanogaster],
    #emph[Arabidopsis thaliana].

    한국어 문장 속 #emph[emphasized Latin words] should reveal whether the italic is
    synthesized or true.
  ]

  #colbreak()

  #small_label[SNU Appendard (Inter v4.1 italic)]
  #v(4pt)
  #text(font: "SNU Appendard", size: 11pt)[
    #italic_diagnostics

    Bibliography: Kim, J. (2026). #emph[Mixed-script typography].

    Scientific names: #emph[E. coli], #emph[Drosophila melanogaster],
    #emph[Arabidopsis thaliana].

    한국어 문장 속 #emph[emphasized Latin words] should reveal whether the italic is
    synthesized or true.
  ]
]

#pagebreak()
#section[Glyph Table]
#let glyphs = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789.,:;!?()[]{}+-=*/&%$#@"
#table(
  columns: 6,
  inset: 4pt,
  stroke: rgb("#dddddd"),
  ..glyphs.clusters().map(g => [
    #text(font: "SNU Appendard", size: 18pt)[#g]
    #linebreak()
    #text(size: 6pt, fill: rgb("#666666"))[#g]
  ]),
)

#pagebreak()
#section[Print Test Patterns]
#text(font: "Pretendard", size: 9pt)[
Pretendard original OTF: WWW iii 000111 office affine efficient minimum
IIII HHHH mmmm 1234567890 tabular spacing spacing spacing.
]

#v(10pt)

#text(font: "SNU Appendard", size: 9pt)[
SNU Appendard UPM 1000 OTF: WWW iii 000111 office affine efficient minimum
IIII HHHH mmmm 1234567890 tabular spacing spacing spacing.
]

#v(10pt)

#for i in range(8) [
  #text(font: "SNU Appendard", size: 8pt)[The quick brown fox jumps over 0123456789 mixed 한국어 text.]
  #linebreak()
]
