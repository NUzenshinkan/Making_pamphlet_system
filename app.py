import streamlit as st
import pandas as pd
from PIL import Image, ImageDraw, ImageFont, ImageOps
import os
import re
import gdown
from pdf2image import convert_from_path

# ==========================================
# 1. ページ設定とUI
# ==========================================
st.set_page_config(page_title="おめぱん自動生成システム", layout="centered")
st.title("おめぱん自動生成システム")
st.write("CSVデータと背景画像をアップロードするだけで、部活・サークル紹介のPDF冊子を自動生成します。")

# 🌟 画面上のマニュアル部分
with st.expander("０．📖 使い方", expanded=True):
    st.markdown("""
    **【最初にやって欲しいこと】**
    1. **文字数制限**: Googleフォームの紹介文はレイアウトに合わせて字数制限を設けてください。
    2. **画像フォルダの権限**: 回答画像が保存されるGoogleドライブのフォルダは、作業中のみアクセス権を「リンクを知っている全員」に変更してください（終わったら戻してOKです）。

    **【操作手順】**
    １．下のプルダウンからお好みの「レイアウト」を選びます。
    ２．フォームからダウンロードした「CSVデータ」をアップロードします。
    ３．「部活用」と「サークル用」の背景画像（JPG/PNG）をアップロードします。
    ４．「🚀 PDFを生成する」ボタンを押してしばらく待ちます。
    ５．下に出てくるボタンから完成したPDFをダウンロード！
    """)
    
    # === 今回の追加部分：マニュアルPDFのダウンロードボタン ===
    if os.path.exists("manual.pdf"):
        with open("manual.pdf", "rb") as f:
            st.download_button(
                label="📄 印刷・配布用のマニュアルPDFをダウンロード",
                data=f,
                file_name="新歓パンフ自動生成システム_マニュアル.pdf",
                mime="application/pdf"
            )

# 設定エリア
st.header("１．設定とファイルのアップロード")
layout_mode = st.selectbox(
    "📝 レイアウトを選択してください",
    ["田の字", "目の字", "1枠回り込み", "1枠縦積み"]
)

csv_file = st.file_uploader("📊 回答データのCSV", type=["csv"])
bg_bukatsu_file = st.file_uploader("🖼️ 部活用の背景画像", type=["jpg", "jpeg", "png"])
bg_circle_file = st.file_uploader("🖼️ サークル用の背景画像", type=["jpg", "jpeg", "png"])

FONT_PATH_TITLE = "NotoSansJP-Medium.ttf"
FONT_PATH_TEXT = "NotoSansJP-Regular.ttf"

# ==========================================
# 2. 内部エンジン（画像処理・PDF生成）
# ==========================================
def wrap_japanese_text(text, font, draw_obj, max_w):
    lines = str(text).split('\n')
    wrapped_lines = []
    kinsoku = "。、，．！？!?”’)】」』"
    for line in lines:
        current_line = ""
        for char in line:
            if draw_obj.textlength(current_line + char, font=font) <= max_w:
                current_line += char
            else:
                if char in kinsoku: current_line += char
                else:
                    wrapped_lines.append(current_line)
                    current_line = char
        if current_line: wrapped_lines.append(current_line)
    return "\n".join(wrapped_lines)

def wrap_and_draw_floating_text(text, font, draw_obj, x1, y1, photo_w, photo_h, full_w, gap, do_draw=True):
    lines = str(text).split('\n')
    kinsoku = "。、，．！？!?”’)】」』"
    line_height = int(font.size * 1.5) 
    current_y = y1
    right_x = x1 + photo_w + gap
    right_w = full_w - photo_w - gap
    margin_bottom = int(font.size * 0.5) 
    for line in lines:
        current_line = ""
        for char in line:
            is_beside_photo = current_y < (y1 + photo_h + margin_bottom)
            current_max_w = right_w if is_beside_photo else full_w
            current_start_x = right_x if is_beside_photo else x1
            if draw_obj.textlength(current_line + char, font=font) <= current_max_w:
                current_line += char
            else:
                if char in kinsoku: current_line += char
                else:
                    if do_draw: draw_obj.text((current_start_x, current_y), current_line, font=font, fill=(0, 0, 0))
                    current_y += line_height
                    is_beside_photo = current_y < (y1 + photo_h + margin_bottom)
                    current_line = char
        if current_line:
            is_beside_photo = current_y < (y1 + photo_h + margin_bottom)
            current_start_x = right_x if is_beside_photo else x1
            if do_draw: draw_obj.text((current_start_x, current_y), current_line, font=font, fill=(0, 0, 0))
            current_y += line_height
    return current_y

def get_items_per_page(mode):
    if mode == "田の字": return 4
    elif mode == "目の字": return 3
    else: return 1

def calculate_slots(mode, bg_w, bg_h):
    margin_x, margin_top, margin_bottom = int(bg_w * 0.08), int(bg_h * 0.12), int(bg_h * 0.08)
    gap_x, gap_y = int(bg_w * 0.04), int(bg_h * 0.04)
    slots = []
    if mode == "田の字":
        mid_x, mid_y = bg_w // 2, bg_h // 2
        slots = [
            (margin_x, margin_top, mid_x - gap_x//2, mid_y - gap_y//2),
            (mid_x + gap_x//2, margin_top, bg_w - margin_x, mid_y - gap_y//2),
            (margin_x, mid_y + gap_y//2, mid_x - gap_x//2, bg_h - margin_bottom),
            (mid_x + gap_x//2, mid_y + gap_y//2, bg_w - margin_x, bg_h - margin_bottom)
        ]
    elif mode == "目の字":
        slot_height = (bg_h - margin_top - margin_bottom - (gap_y * 2)) // 3
        for k in range(3):
            y_start = margin_top + (slot_height + gap_y) * k
            slots.append((margin_x, y_start, bg_w - margin_x, y_start + slot_height))
    else:
        slots = [(margin_x, margin_top, bg_w - margin_x, bg_h - margin_bottom)]
    return slots

def process_slot(bg_img, data_row, slot_coords, mode):
    x1, y1, x2, y2 = slot_coords
    slot_w, slot_h = x2 - x1, y2 - y1
    draw = ImageDraw.Draw(bg_img)

    longer_str = max(str(data_row['写真']), str(data_row.get('ビラデータ', '')), key=len)
    file_id_match = re.search(r'id=([a-zA-Z0-9_-]+)', longer_str)
    if not file_id_match: return

    temp_img_path = f"temp_{file_id_match.group(1)}.jpg"
    dl_url = f'https://drive.google.com/uc?id={file_id_match.group(1)}'
    gdown.download(dl_url, temp_img_path, quiet=True)
    
    try: content_img = Image.open(temp_img_path).convert("RGB")
    except:
        try: content_img = convert_from_path(temp_img_path, first_page=1, last_page=1, dpi=300)[0].convert("RGB")
        except: return

    if data_row.get('原稿タイプ', '') == 'ビラデータ':
        bg_img.paste(ImageOps.pad(content_img, (slot_w, slot_h), color=(255, 255, 255), method=Image.Resampling.LANCZOS), (x1, y1))
        if os.path.exists(temp_img_path): os.remove(temp_img_path)
        return

    title_text = str(data_row['団体名'])
    text_data = str(data_row['紹介文'])

    if mode == "田の字":
        base_t_size, base_txt_size, ph_h, spc = int(slot_h*0.08), int(slot_h*0.045), int(slot_h*0.45), int(slot_h*0.03)
        cur_t_size = base_t_size
        t_font = ImageFont.truetype(FONT_PATH_TITLE, cur_t_size)
        while draw.textlength(title_text, font=t_font) > slot_w and cur_t_size > 10:
            cur_t_size -= 2
            t_font = ImageFont.truetype(FONT_PATH_TITLE, cur_t_size)
        draw.text((x1, y1), title_text, font=t_font, fill=(0, 0, 0))
        ph_y = y1 + cur_t_size + spc
        bg_img.paste(ImageOps.pad(content_img, (slot_w, ph_h), color=(255, 255, 255), method=Image.Resampling.LANCZOS), (x1, ph_y))
        txt_y = ph_y + ph_h + spc
        max_h = (y1 + slot_h) - txt_y
        cur_txt_size = base_txt_size
        while True:
            txt_font = ImageFont.truetype(FONT_PATH_TEXT, cur_txt_size)
            wrp_txt = wrap_japanese_text(text_data, txt_font, draw, slot_w)
            bbox = draw.multiline_textbbox((0, 0), wrp_txt, font=txt_font, spacing=int(cur_txt_size*0.5))
            if (bbox[3]-bbox[1]) <= max_h or cur_txt_size <= 10: break
            cur_txt_size -= 2
        draw.multiline_text((x1, txt_y), wrp_txt, font=txt_font, fill=(0, 0, 0), spacing=int(cur_txt_size*0.5))

    elif mode == "目の字":
        ph_w, in_gap = int(slot_w*0.35), int(slot_w*0.03)
        txt_area_w = slot_w - ph_w - in_gap
        base_t_size, spc = int(slot_h*0.15), int(slot_h*0.05)
        bg_img.paste(ImageOps.pad(content_img, (ph_w, slot_h), color=(255, 255, 255), method=Image.Resampling.LANCZOS), (x1, y1))
        txt_x = x1 + ph_w + in_gap
        cur_t_size = base_t_size
        t_font = ImageFont.truetype(FONT_PATH_TITLE, cur_t_size)
        while draw.textlength(title_text, font=t_font) > txt_area_w and cur_t_size > 10:
            cur_t_size -= 2
            t_font = ImageFont.truetype(FONT_PATH_TITLE, cur_t_size)
        draw.text((txt_x, y1), title_text, font=t_font, fill=(0, 0, 0))
        txt_y = y1 + cur_t_size + spc
        max_h = (y1 + slot_h) - txt_y
        cur_txt_size = int(slot_h*0.08)
        while True:
            txt_font = ImageFont.truetype(FONT_PATH_TEXT, cur_txt_size)
            wrp_txt = wrap_japanese_text(text_data, txt_font, draw, txt_area_w)
            bbox = draw.multiline_textbbox((0, 0), wrp_txt, font=txt_font, spacing=int(cur_txt_size*0.5))
            if (bbox[3]-bbox[1]) <= max_h or cur_txt_size <= 10: break
            cur_txt_size -= 2
        draw.multiline_text((txt_x, txt_y), wrp_txt, font=txt_font, fill=(0, 0, 0), spacing=int(cur_txt_size*0.5))

    elif mode == "1枠回り込み":
        ph_w, ph_h, gap = int(slot_w*0.45), int(slot_h*0.35), int(slot_w*0.03)
        cur_t_size, spc = int(slot_h*0.06), int(slot_h*0.03)
        t_font = ImageFont.truetype(FONT_PATH_TITLE, cur_t_size)
        while draw.textlength(title_text, font=t_font) > slot_w and cur_t_size > 10:
            cur_t_size -= 2
            t_font = ImageFont.truetype(FONT_PATH_TITLE, cur_t_size)
        draw.text((x1, y1), title_text, font=t_font, fill=(0, 0, 0))
        con_y = y1 + cur_t_size + spc
        bg_img.paste(ImageOps.pad(content_img, (ph_w, ph_h), color=(255, 255, 255), method=Image.Resampling.LANCZOS), (x1, con_y))
        cur_txt_size = int(slot_h*0.03)
        while True:
            txt_font = ImageFont.truetype(FONT_PATH_TEXT, cur_txt_size)
            bot_y = wrap_and_draw_floating_text(text_data, txt_font, draw, x1, con_y, ph_w, ph_h, slot_w, gap, do_draw=False)
            if bot_y <= (y1 + slot_h) or cur_txt_size <= 10: break
            cur_txt_size -= 2
        wrap_and_draw_floating_text(text_data, txt_font, draw, x1, con_y, ph_w, ph_h, slot_w, gap, do_draw=True)

    elif mode == "1枠縦積み":
        ph_h = int(slot_h*0.40)
        cur_t_size, spc = int(slot_h*0.07), int(slot_h*0.04)
        t_font = ImageFont.truetype(FONT_PATH_TITLE, cur_t_size)
        while draw.textlength(title_text, font=t_font) > slot_w and cur_t_size > 10:
            cur_t_size -= 2
            t_font = ImageFont.truetype(FONT_PATH_TITLE, cur_t_size)
        draw.text((x1, y1), title_text, font=t_font, fill=(0, 0, 0))
        ph_y = y1 + cur_t_size + spc
        bg_img.paste(ImageOps.pad(content_img, (slot_w, ph_h), color=(255, 255, 255), method=Image.Resampling.LANCZOS), (x1, ph_y))
        txt_y = ph_y + ph_h + spc
        max_h = (y1 + slot_h) - txt_y
        cur_txt_size = int(slot_h*0.04)
        while True:
            txt_font = ImageFont.truetype(FONT_PATH_TEXT, cur_txt_size)
            wrp_txt = wrap_japanese_text(text_data, txt_font, draw, slot_w)
            bbox = draw.multiline_textbbox((0, 0), wrp_txt, font=txt_font, spacing=int(cur_txt_size*0.5))
            if (bbox[3]-bbox[1]) <= max_h or cur_txt_size <= 10: break
            cur_txt_size -= 2
        draw.multiline_text((x1, txt_y), wrp_txt, font=txt_font, fill=(0, 0, 0), spacing=int(cur_txt_size*0.5))

    if os.path.exists(temp_img_path): os.remove(temp_img_path)

def generate_pages_only(df, bg_image, mode):
    pages, step = [], get_items_per_page(mode)
    if df.empty: return []
    for i in range(0, len(df), step):
        chunk = df.iloc[i:i+step]
        page_img = bg_image.copy()
        slots = calculate_slots(mode, page_img.size[0], page_img.size[1])
        for j, (_, row) in enumerate(chunk.iterrows()):
            process_slot(page_img, row, slots[j], mode)
        page_img.info['dpi'] = (300, 300)
        pages.append(page_img)
    return pages

def generate_toc_pages(df, bg_image, title_text, start_page_num, mode):
    if df.empty: return []
    step = get_items_per_page(mode)
    base_bg = bg_image.copy()
    bg_w, bg_h = base_bg.size
    margin_x, margin_y = int(bg_w * 0.1), int(bg_h * 0.12)
    font_toc_title = ImageFont.truetype(FONT_PATH_TITLE, 100)
    font_toc_item = ImageFont.truetype(FONT_PATH_TEXT, 45)
    
    items_per_col = 50
    items_per_page = items_per_col * 2
    toc_pages = []
    
    for page_idx in range(0, len(df), items_per_page):
        chunk = df.iloc[page_idx : page_idx + items_per_page]
        page_img = base_bg.copy()
        draw = ImageDraw.Draw(page_img)
        draw.text((margin_x, margin_y - 120), f"■ {title_text}", font=font_toc_title, fill=(0, 0, 0))
        y_start, col_width = margin_y + 80, int(bg_w * 0.4)
        
        for i, (orig_idx, row) in enumerate(chunk.iterrows()):
            global_idx = page_idx + i
            p_num = start_page_num + (global_idx // step)
            col, row_in_col = i // items_per_col, i % items_per_col
            x = margin_x + (col * col_width) + (col * 150)
            y = y_start + (row_in_col * 60)
            name = str(row['団体名'])
            while draw.textlength(name, font=font_toc_item) > (col_width - 100):
                name = name[:-2] + "…"
            draw.text((x, y), name, font=font_toc_item, fill=(0, 0, 0))
            draw.text((x + col_width - 50, y), f"p.{p_num}", font=font_toc_item, fill=(0, 0, 0))
            dot_x_start = x + draw.textlength(name, font=font_toc_item) + 20
            dot_x_end = x + col_width - 70
            draw.text((dot_x_start, y), "." * int((dot_x_end - dot_x_start)/15), font=font_toc_item, fill=(150, 150, 150))
        page_img.info['dpi'] = (300, 300)
        toc_pages.append(page_img)
    return toc_pages

# ==========================================
# 3. 実行ボタンとダウンロード
# ==========================================
st.header("２．PDFの生成")
if st.button("PDFを生成する"):
    if csv_file and bg_bukatsu_file and bg_circle_file:
        try:
            with st.spinner("画像のダウンロードとPDFの生成を行っています。しばらくお待ちください..."):
                df = pd.read_csv(csv_file)
                df_bukatsu = df[df['区分'] == '部活']
                df_circle = df[df['区分'] == 'サークル']

                # 背景画像をメモリ上で開く
                bg_b_img = Image.open(bg_bukatsu_file).convert("RGB")
                bg_c_img = Image.open(bg_circle_file).convert("RGB")

                # --- 部活PDFの生成 ---
                pages_bukatsu = generate_pages_only(df_bukatsu, bg_b_img, layout_mode)
                toc_bukatsu = generate_toc_pages(df_bukatsu, bg_b_img, "部活 目次", 1, layout_mode)
                if pages_bukatsu:
                    out_b = toc_bukatsu + pages_bukatsu
                    out_b[0].save("部活.pdf", save_all=True, append_images=out_b[1:], resolution=300.0)

                # --- サークルPDFの生成 ---
                pages_circle = generate_pages_only(df_circle, bg_c_img, layout_mode)
                toc_circle = generate_toc_pages(df_circle, bg_c_img, "サークル 目次", 1, layout_mode)
                if pages_circle:
                    out_c = toc_circle + pages_circle
                    out_c[0].save("サークル.pdf", save_all=True, append_images=out_c[1:], resolution=300.0)

            st.success("✅ 生成が完了しました！以下のボタンからダウンロードしてください。")
            
            # ダウンロードボタンの表示
            col1, col2 = st.columns(2)
            if os.path.exists("部活.pdf"):
                with open("部活.pdf", "rb") as f:
                    col1.download_button("📥 部活.pdf をダウンロード", f, file_name="部活パンフレット.pdf")
            if os.path.exists("サークル.pdf"):
                with open("サークル.pdf", "rb") as f:
                    col2.download_button("📥 サークル.pdf をダウンロード", f, file_name="サークルパンフレット.pdf")

        except Exception as e:
            st.error(f"エラーが発生しました: {e}")
    else:
        st.warning("⚠️ CSVと2つの背景画像をすべてアップロードしてください。")