"""Sinh 4 trang A4 chua 40 danh thiep HU CAU de in, cat va chup lai.

VI SAO CAN CONG CU NAY

Khong co bo du lieu danh thiep cong khai nao kem san nhan van ban, ca tieng
Anh lan tieng Nhat. Phan tieng Nhat bat buoc phai tu tao.

Cai kho khi danh gia OCR khong phai la co duoc chu, ma la co duoc ANH XUONG
CAP DUNG KIEU THUC TE: nghieng, mo, choi den, bong tay, van giay. File PNG
sac net cho ket qua lac quan vo dung. Vi vay quy trinh la:

    sinh trang A4  ->  IN RA GIAY  ->  cat roi  ->  CHUP BANG DIEN THOAI

Nhan chuan duoc sinh tu chinh du lieu dung de ve the, nen chinh xac tuyet doi
- khong phai go tay, va khong the go sai.

CACH DUNG

    python backend/scripts/make_card_sheets.py

Ket qua:
    datasets/print/sheet-ja-dev.png     10 the tieng Nhat  -> dev/ja/001..010
    datasets/print/sheet-ja-eval.png    10 the tieng Nhat  -> eval/ja/001..010
    datasets/print/sheet-en-dev.png     10 the tieng Anh   -> dev/en/001..010
    datasets/print/sheet-en-eval.png    10 the tieng Anh   -> eval/en/001..010
    datasets/labels.jsonl               nhan chuan cho ca 40 the

MOI TRANG LA MOT SPLIT. Bo dev va bo eval khong dung chung the nao, nen khong
co ro ri du lieu giua hai bo.

IN THE NAO

- In o ty le 100% / "Actual size", KHONG chon "Fit to page" - neu khong the
  se sai kich thuoc that (91x55mm) va anh huong den do phan giai chu.
- Giay thuong la du. Giay anh bong se tao them phan chieu sang, dung cho
  vai tam de thu tinh huong choi den.
- Cat theo duong vien mo. Ma the (JA-D-01...) nam ngoai vien, se bi cat bo -
  no o do de ban giu dung thu tu, khong de OCR doc.

CHUP THE NAO

Sau khi cat, chup lan luot theo dung thu tu tren trang (trai sang phai, tren
xuong duoi) va dat ten 001.jpg ... 010.jpg trong thu muc tuong ung.

Co y tao du cac tinh huong ma Ngay 8 phai kiem thu:
  4 tam nghieng, 2 tam mo, 2 tam choi den, con lai chup thang ro net.

GIOI HAN PHAI NOI RO

The sinh ra khong co logo, khong co nen mau dam, khong co in nhu, khong co
chu doc. Danh thiep that co nhung thu do. Vi vay VAN NEN tron them 10 tam
that cua ban va dong nghiep (co xin phep) vao bo eval.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "datasets" / "print"
DRYRUN_DIR = ROOT / "datasets" / "_dryrun"
FIXTURE_DIR = ROOT / "backend" / "tests" / "fixtures" / "ocr"
LABELS = ROOT / "datasets" / "labels.jsonl"

DPI = 300
MM = DPI / 25.4                      # pixel tren mot milimet
A4 = (int(210 * MM), int(297 * MM))  # 2480 x 3508
CARD = (int(91 * MM), int(55 * MM))  # 1075 x 650 - kich thuoc danh thiep Nhat
COLS, ROWS = 2, 5

# CANH BAO CHO AI THEM THE TIENG HAN HOAC TIENG TRUNG:
#
# Bang nay chi dung duoc cho tieng Nhat va tieng Anh. YuGothic KHONG co glyph
# Hangul, cung khong co cac chu Han gian the rieng cua tieng Trung. Thieu glyph
# thi Pillow ve o .notdef - MOT O VUONG - chu khong bao loi gi ca.
#
# Nguy hiem o cho: nguoi khong doc duoc tieng Han se nhin trang in thay "co
# chu" va tuong da xong, roi dem di chup 20 tam the toan o vuong.
#
# Do that bang cach so anh ve voi anh cua U+E000 (vung dung rieng, khong font
# nao co glyph, nen no chinh la o .notdef cua font do):
#
#     YuGothic   山=CO  김=THIEU  준=THIEU  这=THIEU  团=THIEU
#     Malgun     山=CO  김=CO     준=CO     这=THIEU  团=THIEU
#     YaHei      山=CO  김=THIEU  준=THIEU  这=CO     团=CO
#
# Muon them tieng Han / tieng Trung thi phai chon font THEO NGON NGU:
#     ko -> C:/Windows/Fonts/malgunbd.ttf, malgun.ttf, malgunsl.ttf
#     zh -> C:/Windows/Fonts/msyhbd.ttc,   msyh.ttc,   msyhl.ttc
# va kiem lai bang phep so o tren TRUOC KHI in.
FONTS = {
    "bold": "C:/Windows/Fonts/YuGothB.ttc",
    "medium": "C:/Windows/Fonts/YuGothM.ttc",
    "regular": "C:/Windows/Fonts/YuGothR.ttc",
    "light": "C:/Windows/Fonts/YuGothL.ttc",
    # YuGothic KHONG co glyph cho dau tieng Viet (ỷ, ệ...) - chu se thanh o
    # vuong. Tieu de trang dung font rieng co ho tro Latin mo rong.
    "latin": "C:/Windows/Fonts/segoeui.ttf",
}
_font_cache: dict[tuple[str, int], ImageFont.FreeTypeFont] = {}


def font(weight: str, pt: float) -> ImageFont.FreeTypeFont:
    px = int(pt * DPI / 72)
    key = (weight, px)
    if key not in _font_cache:
        path = FONTS.get(weight, FONTS["regular"])
        if Path(path).is_file():
            _font_cache[key] = ImageFont.truetype(path, px)
        else:
            _font_cache[key] = ImageFont.load_default(px)
    return _font_cache[key]


# ---------------------------------------------------------------------------
# Du lieu the. MOI GIA TRI O DAY VUA DUNG DE VE VUA DUNG LAM NHAN CHUAN,
# nen nhan khong the lech voi anh.
#
# Ten mien dung example.com / example.co.jp - RFC 2606 danh rieng cho tai lieu,
# khong tro toi to chuc that. So dien thoai va ten deu hu cau.
# ---------------------------------------------------------------------------

JA_DEV = [
    # 1. Day du moi truong
    dict(layout="classic", company="株式会社青葉テクノロジー", dept="営業本部 第一営業部",
         title="部長", name="山田 太郎",
         address="〒100-0001 東京都千代田区千代田1-2-3 青葉ビル7F",
         phones=[("03-5432-1098", "tel", ""), ("090-1234-5678", "mobile", "")],
         email="taro.yamada@example.co.jp", website="https://www.example.co.jp"),
    # 2. Khong co email
    dict(layout="centered", company="有限会社みどり印刷", dept="製造部",
         title="主任", name="鈴木 花子",
         address="〒530-0001 大阪府大阪市北区梅田2-4-9",
         phones=[("06-6345-2100", "tel", "")],
         email=None, website="https://midori-print.example.co.jp"),
    # 3. Khong co website
    dict(layout="split", company="合同会社ひかり物流", dept="配送管理課",
         title="課長", name="佐藤 健一",
         address="〒460-0008 愛知県名古屋市中区栄3-15-1",
         phones=[("052-961-1111", "tel", ""), ("052-961-1112", "fax", "")],
         email="k.sato@example.co.jp", website=None),
    # 4. Co so may le
    dict(layout="classic", company="株式会社さくら食品工業", dept="品質保証部",
         title="係長", name="高橋 美咲",
         address="〒812-0011 福岡県福岡市博多区博多駅前1-1-1",
         phones=[("092-471-3300", "tel", "205")],
         email="misaki.takahashi@example.co.jp", website="https://sakura-foods.example.co.jp"),
    # 5. Ten cong ty dai
    dict(layout="modern", company="一般社団法人日本先端材料技術研究協会",
         dept="研究開発センター", title="主任研究員", name="田中 誠",
         address="〒305-0047 茨城県つくば市千現2-1-6",
         phones=[("029-859-2000", "tel", "")],
         email="m.tanaka@example.or.jp", website="https://www.example.or.jp"),
    # 6. Song ngu Nhat - Anh
    dict(layout="classic", company="株式会社ノヴァシステムズ",
         company_alt="NOVA SYSTEMS CO., LTD.", dept="海外事業部",
         title="マネージャー", name="中村 由美", name_alt="Yumi Nakamura",
         address="〒220-0012 神奈川県横浜市西区みなとみらい3-6-1",
         phones=[("045-222-8800", "tel", ""), ("080-9876-5432", "mobile", "")],
         email="yumi.nakamura@example.co.jp", website="https://www.novasystems.example.com"),
    # 7. Ba so dien thoai
    dict(layout="split", company="株式会社大和建設", dept="工事部",
         title="現場監督", name="小林 大輔",
         address="〒980-0021 宮城県仙台市青葉区中央1-3-1",
         phones=[("022-268-4000", "tel", "12"), ("022-268-4001", "fax", ""),
                 ("070-3344-5566", "mobile", "")],
         email="d.kobayashi@example.co.jp", website=None),
    # 8. Toi thieu
    dict(layout="centered", company="石川デザイン事務所", dept=None,
         title="代表", name="石川 涼",
         address=None, phones=[("075-343-1200", "tel", "")],
         email="ishikawa@example.co.jp", website=None),
    # 9. Chuc danh dai
    dict(layout="modern", company="株式会社トウキョウ・データワークス",
         dept="デジタルトランスフォーメーション推進室",
         title="シニアソリューションアーキテクト", name="渡辺 翔太",
         address="〒150-0043 東京都渋谷区道玄坂1-12-1",
         phones=[("03-6455-7700", "tel", "")],
         email="shota.watanabe@example.co.jp", website="https://tdw.example.co.jp"),
    # 10. Khong co dien thoai
    dict(layout="classic", company="株式会社ゆめみらい教育", dept="企画部",
         title="主査", name="伊藤 彩",
         address="〒060-0001 北海道札幌市中央区北一条西2-1",
         phones=[], email="aya.ito@example.co.jp", website="https://yumemirai.example.co.jp"),
]

JA_EVAL = [
    dict(layout="split", company="株式会社北陸精機", dept="生産技術部",
         title="次長", name="岡田 隆", address="〒920-0853 石川県金沢市本町2-15-1",
         phones=[("076-263-8800", "tel", ""), ("090-5555-1212", "mobile", "")],
         email="t.okada@example.co.jp", website="https://hokuriku-seiki.example.co.jp"),
    dict(layout="classic", company="有限会社あおぞら園芸", dept=None,
         title="店長", name="森 久美子", address="〒700-0901 岡山県岡山市北区本町6-30",
         phones=[("086-234-1900", "tel", "")], email=None,
         website="https://aozora-engei.example.co.jp"),
    dict(layout="modern", company="株式会社瀬戸内マリンサービス", dept="運航部",
         title="主任", name="村上 拓也", address="〒760-0011 香川県高松市浜ノ町1-20",
         phones=[("087-822-4400", "tel", ""), ("087-822-4401", "fax", "")],
         email="t.murakami@example.co.jp", website=None),
    dict(layout="centered", company="株式会社ひだまり介護サービス", dept="訪問介護課",
         title="サービス提供責任者", name="松本 恵子",
         address="〒390-0811 長野県松本市中央1-2-8",
         phones=[("0263-35-7700", "tel", "31")],
         email="k.matsumoto@example.co.jp", website="https://hidamari.example.co.jp"),
    dict(layout="classic", company="公益財団法人東海環境保全機構", dept="調査研究部",
         title="上席研究員", name="斎藤 浩二",
         address="〒420-0853 静岡県静岡市葵区追手町9-6",
         phones=[("054-221-2000", "tel", "")], email="k.saito@example.or.jp",
         website="https://www.tokai-kankyo.example.or.jp"),
    dict(layout="classic", company="株式会社ミナトフーズ", company_alt="MINATO FOODS INC.",
         dept="商品開発部", title="部長代理", name="清水 直樹", name_alt="Naoki Shimizu",
         address="〒650-0024 兵庫県神戸市中央区海岸通5-1-1",
         phones=[("078-333-6600", "tel", ""), ("080-2233-4455", "mobile", "")],
         email="n.shimizu@example.co.jp", website="https://minatofoods.example.com"),
    dict(layout="split", company="株式会社九州システムデザイン", dept="システム開発部",
         title="チームリーダー", name="福田 智子",
         address="〒860-0047 熊本県熊本市西区春日3-15-30",
         phones=[("096-352-1800", "tel", "44"), ("096-352-1801", "fax", ""),
                 ("070-8899-0011", "mobile", "")],
         email="t.fukuda@example.co.jp", website=None),
    dict(layout="centered", company="長谷川写真館", dept=None, title="代表取締役",
         title_extra=None, name="長谷川 明", address=None,
         phones=[("0552-22-3300", "tel", "")], email="hasegawa@example.co.jp",
         website=None),
    dict(layout="modern", company="株式会社アーバンリノベーション東北",
         dept="住宅リフォーム事業部", title="チーフコンサルタント", name="木村 大地",
         address="〒990-0031 山形県山形市十日町1-1-1",
         phones=[("023-622-5500", "tel", "")], email="d.kimura@example.co.jp",
         website="https://urban-reno.example.co.jp"),
    dict(layout="classic", company="株式会社そらいろ出版", dept="編集部",
         title="編集長", name="井上 麻衣", address="〒101-0051 東京都千代田区神田神保町1-3",
         phones=[], email="mai.inoue@example.co.jp", website="https://sorairo-pub.example.co.jp"),
]

EN_DEV = [
    dict(layout="classic", company="Meridian Analytics Inc.", dept="Client Solutions",
         title="Senior Account Manager", name="Jane Doe",
         address="500 Market Street, Suite 200\nSan Francisco, CA 94105",
         phones=[("+1 (415) 555-0142", "tel", ""), ("+1 (415) 555-0199", "mobile", "")],
         email="jane.doe@example.com", website="https://www.example.com"),
    dict(layout="centered", company="Bridgeport Logistics Ltd.", dept="Operations",
         title="Fleet Coordinator", name="Michael Brennan",
         address="12 Harbour Road\nLiverpool L3 4AA, United Kingdom",
         phones=[("+44 151 555 0176", "tel", "")], email=None,
         website="https://bridgeport.example.com"),
    dict(layout="split", company="Northwind Precision Tools", dept="Engineering",
         title="Lead Design Engineer", name="Sarah Okafor",
         address="880 Industrial Parkway\nCleveland, OH 44114",
         phones=[("+1 (216) 555-0108", "tel", ""), ("+1 (216) 555-0109", "fax", "")],
         email="s.okafor@example.com", website=None),
    dict(layout="classic", company="Lumen Health Partners", dept="Regulatory Affairs",
         title="Compliance Officer", name="David Kim",
         address="7 Raffles Place, #21-03\nSingapore 048616",
         phones=[("+65 6555 0133", "tel", "412")], email="david.kim@example.com",
         website="https://lumenhealth.example.com"),
    dict(layout="modern", company="International Federation of Sustainable Packaging Research",
         dept="Policy Division", title="Programme Officer", name="Elena Vasquez",
         address="Rue de la Loi 155\n1040 Brussels, Belgium",
         phones=[("+32 2 555 0190", "tel", "")], email="e.vasquez@example.org",
         website="https://www.example.org"),
    dict(layout="classic", company="Kestrel Marine Surveys", dept="Field Operations",
         title="Senior Surveyor", name="Thomas Lindqvist",
         address="Skeppsbron 22\n111 30 Stockholm, Sweden",
         phones=[("+46 8 555 0121", "tel", ""), ("+46 70 555 0122", "mobile", "")],
         email="t.lindqvist@example.com", website="https://kestrel-marine.example.com"),
    dict(layout="split", company="Copperline Construction Group", dept="Project Delivery",
         title="Site Manager", name="Rachel Nwosu",
         address="Level 8, 190 George Street\nSydney NSW 2000, Australia",
         phones=[("+61 2 5550 0177", "tel", "23"), ("+61 2 5550 0178", "fax", ""),
                 ("+61 4 5550 0179", "mobile", "")],
         email="r.nwosu@example.com", website=None),
    dict(layout="centered", company="Alder & Finch Studio", dept=None,
         title="Founder", name="Priya Raman", address=None,
         phones=[("+91 22 5555 0164", "tel", "")], email="priya@example.com",
         website=None),
    dict(layout="modern", company="Cascade Digital Transformation Services",
         dept="Enterprise Architecture", title="Principal Solutions Architect",
         name="Jonas Meyer", address="Friedrichstraße 68\n10117 Berlin, Germany",
         phones=[("+49 30 5550 0155", "tel", "")], email="j.meyer@example.com",
         website="https://cascade-dts.example.com"),
    dict(layout="classic", company="Harborview Education Trust", dept="Curriculum",
         title="Programme Lead", name="Amina Sardar",
         address="45 Queen Street\nToronto, ON M5H 2M9, Canada",
         phones=[], email="a.sardar@example.org", website="https://harborview.example.org"),
]

EN_EVAL = [
    dict(layout="split", company="Ironwood Materials Corp.", dept="Quality Assurance",
         title="QA Director", name="Robert Ashworth",
         address="2400 Foundry Lane\nPittsburgh, PA 15222",
         phones=[("+1 (412) 555-0186", "tel", ""), ("+1 (412) 555-0187", "mobile", "")],
         email="r.ashworth@example.com", website="https://ironwood.example.com"),
    dict(layout="classic", company="Greenfield Horticulture Ltd.", dept=None,
         title="Nursery Manager", name="Caroline Webb",
         address="Mill Lane, Bramley\nGuildford GU5 0BQ, UK",
         phones=[("+44 1483 555012", "tel", "")], email=None,
         website="https://greenfield-hort.example.com"),
    dict(layout="modern", company="Pacific Rim Freight Services", dept="Customs Brokerage",
         title="Senior Broker", name="Hector Alvarez",
         address="1100 Harbor Boulevard\nLong Beach, CA 90802",
         phones=[("+1 (562) 555-0143", "tel", ""), ("+1 (562) 555-0144", "fax", "")],
         email="h.alvarez@example.com", website=None),
    dict(layout="centered", company="Silverbrook Care Services", dept="Community Nursing",
         title="Care Team Supervisor", name="Fiona Docherty",
         address="18 Hanover Street\nEdinburgh EH2 2EN, UK",
         phones=[("+44 131 555 0198", "tel", "27")], email="f.docherty@example.com",
         website="https://silverbrook.example.com"),
    dict(layout="classic", company="Atlantic Institute for Coastal Resilience",
         dept="Research Programmes", title="Senior Research Fellow", name="Marcus Bello",
         address="One Ocean Drive\nHalifax, NS B3H 4R2, Canada",
         phones=[("+1 (902) 555-0171", "tel", "")], email="m.bello@example.org",
         website="https://www.aicr.example.org"),
    dict(layout="classic", company="Solstice Beverage Group", dept="Product Innovation",
         title="Head of Development", name="Naomi Fischer",
         address="Bahnhofstrasse 41\n8001 Zürich, Switzerland",
         phones=[("+41 44 555 0129", "tel", ""), ("+41 79 555 0130", "mobile", "")],
         email="n.fischer@example.com", website="https://solstice-bev.example.com"),
    dict(layout="split", company="Redstone Software Partners", dept="Platform Engineering",
         title="Engineering Team Lead", name="Ananya Krishnan",
         address="Prestige Tower, 7th Floor\nBengaluru 560001, India",
         phones=[("+91 80 5555 0116", "tel", "58"), ("+91 80 5555 0117", "fax", ""),
                 ("+91 98 5555 0118", "mobile", "")],
         email="a.krishnan@example.com", website=None),
    dict(layout="centered", company="Whitfield Photography", dept=None, title="Owner",
         name="Daniel Whitfield", address=None,
         phones=[("+1 (503) 555-0152", "tel", "")], email="dan@example.com",
         website=None),
    dict(layout="modern", company="Continental Urban Renewal Consultants",
         dept="Housing Regeneration", title="Principal Consultant", name="Sofia Marchetti",
         address="Via Torino 38\n20123 Milano, Italy",
         phones=[("+39 02 5555 0167", "tel", "")], email="s.marchetti@example.com",
         website="https://curc.example.com"),
    dict(layout="classic", company="Bluewater Press", dept="Editorial",
         title="Managing Editor", name="Owen Radcliffe",
         address="9 Fleet Street\nLondon EC4Y 1AA, UK",
         phones=[], email="o.radcliffe@example.com", website="https://bluewater-press.example.com"),
]

SHEETS = [
    ("sheet-ja-dev", JA_DEV, "ja", "dev", "JA-D"),
    ("sheet-ja-eval", JA_EVAL, "ja", "eval", "JA-E"),
    ("sheet-en-dev", EN_DEV, "en", "dev", "EN-D"),
    ("sheet-en-eval", EN_EVAL, "en", "eval", "EN-E"),
]

INK = (25, 25, 28)
GREY = (95, 95, 100)
RULE = (150, 150, 155)
CUT = (205, 205, 210)


_measure = ImageDraw.Draw(Image.new("RGB", (1, 1)))


def wrap(text: str, f: ImageFont.FreeTypeFont, max_w: int) -> list[str]:
    """Cat mot dong thanh nhieu dong vua be rong cho phep.

    VI SAO BAT BUOC: neu chu tran ra ngoai mep the, anh in ra se MAT mot phan
    noi dung trong khi nhan chuan van ghi day du. Phep do o Ngay 9 se tinh la
    OCR bo sot, trong khi loi thuc ra nam o cong cu sinh the.

    Tieng Nhat khong dung dau cach de tach tu nen cat theo ky tu; tieng Anh
    cat theo tu.
    """
    if _measure.textlength(text, font=f) <= max_w:
        return [text]

    has_space = " " in text.strip()
    units = text.split(" ") if has_space else list(text)
    joiner = " " if has_space else ""

    lines, current = [], ""
    for unit in units:
        candidate = (current + joiner + unit) if current else unit
        if _measure.textlength(candidate, font=f) <= max_w or not current:
            current = candidate
        else:
            lines.append(current)
            current = unit
    if current:
        lines.append(current)
    return lines


def fit_font(text: str, weight: str, max_w: int,
             start_pt: float, min_pt: float) -> ImageFont.FreeTypeFont:
    """Chon co chu lon nhat ma van vua mot dong.

    Ngat "合同会社ひかり物流" thanh "合同会社ひかり物" + "流" vua xau vua khong
    giong the that - nha thiet ke se thu nho chu. Ngat giua chu con co the
    khien OCR tach thanh hai khoi rieng.
    """
    pt = start_pt
    while pt > min_pt:
        f = font(weight, pt)
        if _measure.textlength(text, font=f) <= max_w:
            return f
        pt -= 0.5
    return font(weight, min_pt)


def fit_block(lines: list[str], weight: str, max_w: int, avail_h: int,
              start_pt: float, min_pt: float, gap: float = 1.45):
    """Chon co chu lon nhat ma ca khoi van vua chieu cao con lai.

    VI SAO BAT BUOC: ten cong ty dai xuong hai dong lam khoi phia tren cao
    them, nhung khoi lien he lai tinh vi tri theo mot dong - hai khoi de len
    nhau. Anh in ra se co chu chong chu, khong doc duoc, trong khi nhan chuan
    van ghi day du. Loi nam o cong cu sinh the chu khong phai o OCR.
    """
    pt = start_pt
    while True:
        f = font(weight, pt)
        wrapped = [part for line in lines for part in wrap(line, f, max_w)]
        height = int(len(wrapped) * f.size * gap)
        if height <= avail_h or pt <= min_pt:
            return f, wrapped, height
        pt -= 0.5


def phone_line(value: str, label: str, ext: str, lang: str) -> str:
    prefix = {"tel": "TEL", "fax": "FAX", "mobile": "携帯" if lang == "ja" else "Mobile"}
    line = prefix.get(label, "TEL") + ": " + value
    if ext:
        line += ("（内線 " + ext + "）") if lang == "ja" else ("  ext. " + ext)
    return line


def contact_lines(card: dict, lang: str) -> list[str]:
    lines = []
    if card.get("address"):
        lines.extend(card["address"].split("\n"))
    for value, label, ext in card.get("phones", []):
        lines.append(phone_line(value, label, ext, lang))
    if card.get("email"):
        lines.append(card["email"])
    if card.get("website"):
        lines.append(card["website"])
    return lines


def render_card(card: dict, lang: str) -> Image.Image:
    """Ve mot the. Bo cuc thay doi theo `layout` de bo mau da dang hon."""
    w, h = CARD
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)
    layout = card.get("layout", "classic")
    pad = int(6 * MM)

    body = contact_lines(card, lang)
    f_company = font("bold", 10.5)
    f_alt = font("light", 7)
    f_dept = font("regular", 7.5)
    f_title = font("regular", 8)
    f_name = font("bold", 15)
    f_name_alt = font("light", 7.5)
    f_body = font("regular", 7.5)

    def block(x: int, y: int, lines: list[str], f, fill=INK, gap: float = 1.45,
              max_w: int | None = None) -> int:
        limit = max_w if max_w is not None else w - x - pad
        for line in lines:
            for part in wrap(line, f, limit):
                d.text((x, y), part, font=f, fill=fill)
                y += int(f.size * gap)
        return y

    if layout == "centered":
        y = pad + int(2 * MM)
        for text, f, fill in [(card["company"], f_company, INK),
                              (card.get("company_alt"), f_alt, GREY),
                              (card.get("dept"), f_dept, GREY)]:
            if text:
                for part in wrap(text, f, w - 2 * pad):
                    tw = d.textlength(part, font=f)
                    d.text(((w - tw) / 2, y), part, font=f, fill=fill)
                    y += int(f.size * 1.5)
        y += int(2 * MM)
        if card.get("title"):
            tw = d.textlength(card["title"], font=f_title)
            d.text(((w - tw) / 2, y), card["title"], font=f_title, fill=GREY)
            y += int(f_title.size * 1.6)
        tw = d.textlength(card["name"], font=f_name)
        d.text(((w - tw) / 2, y), card["name"], font=f_name, fill=INK)
        y += int(f_name.size * 1.5)
        d.line([(w * 0.32, y), (w * 0.68, y)], fill=RULE, width=2)
        y += int(3 * MM)
        f_b, wrapped, _ = fit_block(body, "regular", w - 2 * pad, h - pad - y,
                                    7.5, 5.5)
        for part in wrapped:
            tw = d.textlength(part, font=f_b)
            d.text(((w - tw) / 2, y), part, font=f_b, fill=INK)
            y += int(f_b.size * 1.45)

    elif layout == "split":
        # Vach ngan dat o 0.42 (khong phai 0.46) de cot lien he du rong cho
        # dia chi tieng Nhat day du.
        split_x = int(w * 0.47)
        left_w = split_x - pad - int(2 * MM)
        right_x = split_x + int(3 * MM)
        right_w = w - pad - right_x

        d.line([(split_x, pad), (split_x, h - pad)], fill=RULE, width=2)
        y = pad + int(3 * MM)
        y = block(pad, y, [card["company"]],
                  fit_font(card["company"], "bold", left_w, 10.5, 7.5),
                  max_w=left_w)
        if card.get("dept"):
            y = block(pad, y + 4, [card["dept"]], f_dept, GREY, max_w=left_w)
        y += int(4 * MM)
        if card.get("title"):
            y = block(pad, y, [card["title"]], f_title, GREY, max_w=left_w)
        block(pad, y + 4, [card["name"]], f_name, max_w=left_w)
        right_top = pad + int(4 * MM)
        f_b, wrapped, _ = fit_block(body, "regular", right_w,
                                    h - pad - right_top, 7.0, 5.5)
        block(right_x, right_top, wrapped, f_b, max_w=right_w)

    elif layout == "modern":
        y = pad + int(3 * MM)
        y = block(pad, y, [card["name"]], f_name)
        if card.get("name_alt"):
            y = block(pad, y, [card["name_alt"]], f_name_alt, GREY)
        y += int(1 * MM)
        if card.get("title"):
            y = block(pad, y, [card["title"]], f_title, GREY)
        y += int(3 * MM)
        y = block(pad, y,
                  [card["company"]],
                  fit_font(card["company"], "bold", w - 2 * pad, 10.5, 8.0))
        if card.get("dept"):
            y = block(pad, y, [card["dept"]], f_dept, GREY)
        # Khoi tren da ve xong tai y. Phan con lai la tat ca cho khoi lien he
        # duoc phep chiem - tinh tu day thay vi gia dinh mot chieu cao co dinh.
        avail = h - pad - y - int(2 * MM)
        f_b, wrapped, height = fit_block(body, "regular", w - 2 * pad, avail, 7.5, 5.5)
        start = max(y + int(2 * MM), h - pad - height)
        block(pad, start, wrapped, f_b)

    else:  # classic
        y = pad + int(2 * MM)
        y = block(pad, y, [card["company"]],
                  fit_font(card["company"], "bold", w - 2 * pad, 10.5, 8.0))
        if card.get("company_alt"):
            y = block(pad, y, [card["company_alt"]], f_alt, GREY)
        if card.get("dept"):
            y = block(pad, y + 2, [card["dept"]], f_dept, GREY)
        y += int(4 * MM)
        if card.get("title"):
            y = block(pad, y, [card["title"]], f_title, GREY)
        y = block(pad, y + 2, [card["name"]], f_name)
        if card.get("name_alt"):
            y = block(pad, y, [card["name_alt"]], f_name_alt, GREY)
        y += int(2 * MM)
        d.line([(pad, y), (w - pad, y)], fill=RULE, width=2)
        top = y + int(2.5 * MM)
        f_b, wrapped, _ = fit_block(body, "regular", w - 2 * pad,
                                    h - pad - top, 7.5, 5.5)
        block(pad, top, wrapped, f_b)

    return img


def render_sheet(cards: list[dict], lang: str, code: str, out: Path) -> None:
    sheet = Image.new("RGB", A4, "white")
    d = ImageDraw.Draw(sheet)
    grid_w, grid_h = COLS * CARD[0], ROWS * CARD[1]
    x0, y0 = (A4[0] - grid_w) // 2, (A4[1] - grid_h) // 2
    f_id = font("regular", 7)

    for index, card in enumerate(cards):
        col, row = index % COLS, index // COLS
        x, y = x0 + col * CARD[0], y0 + row * CARD[1]
        sheet.paste(render_card(card, lang), (x, y))
        d.rectangle([x, y, x + CARD[0] - 1, y + CARD[1] - 1], outline=CUT, width=1)

        # Ma the nam NGOAI vien, trong le trang - se bi cat bo khi cat the.
        # No o day de ban giu dung thu tu, khong de OCR doc duoc.
        tag = f"{code}-{index + 1:02d}"
        label = Image.new("RGB", (int(f_id.size * len(tag) * 0.75), int(f_id.size * 1.4)),
                          "white")
        ImageDraw.Draw(label).text((0, 0), tag, font=f_id, fill=GREY)
        label = label.rotate(90, expand=True)
        lx = x - label.width - int(1.5 * MM) if col == 0 else x + CARD[0] + int(1.5 * MM)
        sheet.paste(label, (max(0, lx), y + (CARD[1] - label.height) // 2))

    d.text((x0, y0 - int(9 * MM)),
           f"{out.stem}  —  in ở tỷ lệ 100% (Actual size), không dùng Fit to page",
           font=font("latin", 8), fill=GREY)

    out.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out, dpi=(DPI, DPI))


def ocr_text(card: dict, lang: str) -> str:
    """Van ban theo dung thu tu doc tren the - dung lam fixture cho che do kho."""
    lines = [card["company"]]
    if card.get("company_alt"):
        lines.append(card["company_alt"])
    if card.get("dept"):
        lines.append(card["dept"])
    if card.get("title"):
        lines.append(card["title"])
    lines.append(card["name"])
    if card.get("name_alt"):
        lines.append(card["name_alt"])
    lines.extend(contact_lines(card, lang))
    return "\n".join(lines)


def write_dry_run(card: dict, lang: str, split: str, index: int) -> Path:
    """Cat mot the thanh anh rieng + fixture OCR, de chay thu duong do.

    CANH BAO PHAM VI: day la anh so sac net tuyet doi, KHONG phai anh chup.
    No chi dung de kiem chung `evaluate.py` chay dung, tuyet doi khong dung
    de bao cao chat luong - se cho con so lac quan vo nghia.

    Vi vay anh duoc ghi vao `datasets/_dryrun/`, tach hoan toan khoi
    `datasets/dev|eval/` la noi danh cho anh chup that.
    """
    image = render_card(card, lang)
    out = DRYRUN_DIR / split / lang / f"{index + 1:03d}.jpg"
    out.parent.mkdir(parents=True, exist_ok=True)
    image.save(out, quality=92)

    FIXTURE_DIR.mkdir(parents=True, exist_ok=True)
    digest = hashlib.sha256(out.read_bytes()).hexdigest()
    (FIXTURE_DIR / f"{digest}.json").write_text(
        json.dumps({
            "source_file": out.name,
            "raw_text": ocr_text(card, lang),
            "provider": "synthetic",
            "provider_version": "make_card_sheets --crop",
            "detected_languages": [lang],
            "blocks": [],
            "payload": {"note": "van ban da biet, khong qua OCR"},
        }, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out


def label_row(card: dict, lang: str, split: str, index: int) -> dict:
    row = {
        "image": f"{split}/{lang}/{index + 1:03d}.jpg",
        "lang": lang,
        "full_name": card["name"],
        "company_name": card["company"],
        "job_titles": [card["title"]] if card.get("title") else [],
        "departments": [card["dept"]] if card.get("dept") else [],
        "emails": [card["email"]] if card.get("email") else [],
        "phones": [
            {"value": v, "label": lb, **({"extension": e} if e else {})}
            for v, lb, e in card.get("phones", [])
        ],
        "websites": [card["website"]] if card.get("website") else [],
        "addresses": [card["address"].replace("\n", " ")] if card.get("address") else [],
        "uncertain": [],
    }
    if card.get("name_alt"):
        row["full_name_alt"] = card["name_alt"]
    if card.get("company_alt"):
        row["company_name_alt"] = card["company_alt"]
    return row


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Sinh trang A4 danh thiếp mẫu")
    parser.add_argument("--crop", action="store_true",
                        help="Cắt thêm từng thẻ thành ảnh riêng + fixture, "
                             "để chạy thử evaluate.py khi chưa có ảnh chụp")
    args = parser.parse_args()

    missing_fonts = [p for p in FONTS.values() if not Path(p).is_file()]
    if missing_fonts:
        print("Canh bao: thieu font, chu Nhat co the khong hien dung:")
        for p in missing_fonts:
            print("  ", p)

    rows: list[dict] = []
    for name, cards, lang, split, code in SHEETS:
        if len(cards) != COLS * ROWS:
            raise SystemExit(f"{name}: can {COLS * ROWS} the, dang co {len(cards)}")
        out = OUT_DIR / f"{name}.png"
        render_sheet(cards, lang, code, out)
        rows.extend(label_row(c, lang, split, i) for i, c in enumerate(cards))
        print(f"Da tao {out.relative_to(ROOT)}  ({len(cards)} thẻ -> {split}/{lang}/)")
        if args.crop:
            for i, c in enumerate(cards):
                write_dry_run(c, lang, split, i)
            print(f"        + {len(cards)} ảnh chạy khô trong "
                  f"datasets/_dryrun/{split}/{lang}/")

    if LABELS.is_file():
        backup = LABELS.with_suffix(".jsonl.bak")
        shutil.copy2(LABELS, backup)
        print(f"\nĐã sao lưu nhãn cũ: {backup.relative_to(ROOT)}")

    LABELS.write_text(
        "\n".join(json.dumps(r, ensure_ascii=False) for r in rows) + "\n",
        encoding="utf-8",
    )
    print(f"Đã ghi {len(rows)} nhãn chuẩn: {LABELS.relative_to(ROOT)}")

    print("\nTiếp theo:")
    print("  1. In 4 file PNG ở tỷ lệ 100% (Actual size), KHÔNG chọn Fit to page")
    print("  2. Cắt theo đường viền mờ; mã thẻ ở lề sẽ bị cắt bỏ")
    print("  3. Chụp từng thẻ theo đúng thứ tự trái→phải, trên→dưới")
    print("  4. Lưu vào datasets/dev/ja/001.jpg ... datasets/eval/en/010.jpg")
    print("  5. Kiểm tra: python backend/scripts/check_labels.py")
    print("\nCố ý chụp đa dạng: 4 tấm nghiêng, 2 tấm mờ, 2 tấm chói đèn.")
    if args.crop:
        print("\nẢnh chạy khô đã sẵn sàng. Thử đường đo:")
        print("  python backend/scripts/evaluate.py --split dev "
              "--dataset datasets/_dryrun")
        print("Ảnh đó là ảnh số sắc nét, CHỈ để kiểm chứng công cụ — "
              "không dùng báo cáo chất lượng.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
