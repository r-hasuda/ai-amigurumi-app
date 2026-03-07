import streamlit as st
from google import genai
from huggingface_hub import InferenceClient
import urllib.parse  # 楽天リンクの日本語文字化け防止用に追加
import os
from dotenv import load_dotenv
from PIL import Image
import io
import re
import json

# --- PDF生成用ライブラリ ---
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.lib.fonts import addMapping
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image as ReportLabImage
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors

st.set_page_config(page_title="AIあみぐるみ作家")
# --- ページ設定 ---
st.set_page_config(page_title="AIあみぐるみ作家", page_icon="🧶")

# ==========================================
# 1. 環境変数 / Secrets の読み込み (開発者のキー)
# ==========================================
load_dotenv()
DEV_GOOGLE_KEY = os.getenv("GOOGLE_API_KEY") or st.secrets.get("GOOGLE_API_KEY")
HF_TOKEN = os.getenv("HUGGINGFACE_API_KEY") or st.secrets.get("HUGGINGFACE_API_KEY")

# ==========================================
# 2. サイドバー設定 (ユーザーの任意入力)
# ==========================================
st.sidebar.header("🔑 APIキー設定 (任意)")
st.sidebar.markdown(
    "基本は無料で使えますが、アクセス集中時などにエラーが出る場合、"
    "ご自身のAPIキーを入力すると確実にご利用いただけます。"
)
user_google_key = st.sidebar.text_input("Google Gemini APIキー (任意)", type="password")

st.sidebar.markdown("---")
st.sidebar.header("⚙️ 設定")
target_size = st.sidebar.text_input("仕上がりサイズ", "手のひらサイズ")

# アフィリエイトのトラッキングID
AMAZON_TAG = "hasuda2907-22" 
RAKUTEN_ID = "5170c30d.12d5cbf7.5170c30e.2b43a087" 

# ==========================================
# 3. 使用するAPIキーの決定とクライアント初期化
# ==========================================
active_google_key = user_google_key if user_google_key else DEV_GOOGLE_KEY

if not active_google_key:
    st.error("システムエラー: 開発者のGoogle APIキーが設定されていません。")
    st.stop()
if not HF_TOKEN:
    st.error("システムエラー: 開発者のHugging Faceトークンが設定されていません。")
    st.stop()

client_google = genai.Client(api_key=active_google_key)
client_hf = InferenceClient(api_key=HF_TOKEN)
TEXT_MODEL = "gemini-2.5-flash"

# --- セッションステート初期化 ---
if 'step' not in st.session_state: st.session_state.step = 1
if 'preview_image_bytes' not in st.session_state: st.session_state.preview_image_bytes = None
if 'uploaded_images' not in st.session_state: st.session_state.uploaded_images = []
if 'pattern_text' not in st.session_state: st.session_state.pattern_text = ""
if 'main_yarn_color' not in st.session_state: st.session_state.main_yarn_color = "お好みの色"
# 保持したい項目の初期化
if 'user_feature' not in st.session_state: st.session_state.user_feature = ""
if 'input_image' not in st.session_state: st.session_state.input_image = None

# --- 補助関数群 (変更なし) ---
def parse_json(text):
    try: return json.loads(text)
    except:
        match = re.search(r'```(?:json)?\s*(.*?)\s*```', text, re.DOTALL)
        if match:
            try: return json.loads(match.group(1))
            except: pass
        match = re.search(r'(\{.*\})', text, re.DOTALL)
        if match:
            try: return json.loads(match.group(1))
            except: pass
    return {"is_safe": False, "reason": "解析エラーが発生しました"}

def handle_gemini_api_call(func, *args, **kwargs):
    try:
        return func(*args, **kwargs)
    except Exception as e:
        error_msg = str(e).lower()
        if "429" in error_msg or "quota" in error_msg or "exhausted" in error_msg:
            if not user_google_key:
                st.error("⚠️ 【お知らせ】現在、アプリの無料利用枠の上限に達しています。")
                st.warning("👈 左側のサイドバーに **ご自身のGemini APIキー** を入力していただくと、引き続きすぐにご利用いただけます！")
            else:
                st.error("⚠️ 入力されたAPIキーの利用枠の上限に達したか、無効なキーの可能性があります。")
            st.stop()
        else:
            st.error(f"AI処理中にエラーが発生しました: {e}")
            st.stop()

def check_image_safety(image):
    prompt = """
    Analyze this image for copyright and IP risks.
    Is this a known character from anime, games, movies, or a famous person?
    If it's a generic animal, object, or original character, return is_safe: true.
    Response MUST be in JSON format: {"is_safe": boolean, "reason": "short explanation in Japanese"}
    """
    try:
        res = client_google.models.generate_content(
            model=TEXT_MODEL,
            contents=[prompt, image],
            config={"response_mime_type": "application/json"}
        )
        return parse_json(res.text)
    except Exception as e:
        return {"is_safe": True, "reason": "エラーによりチェックをスキップしました"}

def register_japanese_font():
    font_path = "IPAexGothic.ttf"
    font_name = "IPAexGothic"
    if os.path.exists(font_path):
        try:
            pdfmetrics.registerFont(TTFont(font_name, font_path))
            addMapping(font_name, 0, 0, font_name) 
            addMapping(font_name, 1, 0, font_name) 
            addMapping(font_name, 0, 1, font_name) 
            addMapping(font_name, 1, 1, font_name) 
            return font_name
        except: return "Helvetica"
    return "Helvetica"

def clean_text_for_pdf(text):
    return re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)

def create_styled_pdf(text_content, image_bytes=None):
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=20*mm, leftMargin=20*mm, topMargin=20*mm, bottomMargin=20*mm)
    font_name = register_japanese_font()
    styles = getSampleStyleSheet()
    style_normal = ParagraphStyle(name='JapaneseNormal', parent=styles['Normal'], fontName=font_name, fontSize=10, leading=16)
    style_heading = ParagraphStyle(name='JapaneseHeading', parent=styles['Heading2'], fontName=font_name, fontSize=14, leading=20, spaceBefore=15, spaceAfter=5, textColor=colors.darkblue)
    
    story = []
    story.append(Paragraph("AI Amigurumi Recipe", ParagraphStyle(name='Title', parent=styles['Title'], fontName=font_name, fontSize=20)))
    story.append(Spacer(1, 10*mm))

    if image_bytes:
        img_io = io.BytesIO(image_bytes)
        img = ReportLabImage(img_io)
        img_width = 100 * mm
        aspect = img.imageHeight / float(img.imageWidth)
        img.drawHeight = img_width * aspect
        img.drawWidth = img_width
        story.append(img)
        story.append(Spacer(1, 10*mm))

    lines = text_content.split('\n')
    table_buffer = []

    def flush_table(buffer_list):
        if not buffer_list: return
        data = []
        for row_str in buffer_list:
            # 先頭と末尾の | を除いて分割
            row_str = row_str.strip().strip('|')
            cells = [clean_text_for_pdf(c.strip()) for c in row_str.split('|')]
            if cells: data.append(cells)
    
        if data:
            # 列数を揃える
            max_cols = max(len(row) for row in data)
            data = [row + [''] * (max_cols - len(row)) for row in data]
            
            # セル内のテキストをParagraph化（自動改行のため）
            data_para = [[Paragraph(cell, style_normal) for cell in row] for row in data]
            
            # --- 列幅の計算 (A4横幅 210mm - 余白 40mm = 有効幅 170mm) ---
            # 3列の場合の配分例: [30mm, 40mm, 100mm]
            if max_cols == 3:
                col_widths = [20*mm, 30*mm, 120*mm] 
            elif max_cols == 2:
                col_widths = [50*mm, 120*mm]
            else:
                col_widths = None # 指定なし（自動）

            t = Table(data_para, colWidths=col_widths, hAlign='LEFT', splitByRow=True)
            t.setStyle(TableStyle([
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey), # ヘッダー色
                ('VALIGN', (0, 0), (-1, -1), 'TOP'),              # 上揃え（重要）
                ('LEFTPADDING', (0, 0), (-1, -1), 6),
                ('RIGHTPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('FONTNAME', (0, 0), (-1, -1), font_name),
            ]))
            story.append(t)
            story.append(Spacer(1, 5*mm))

    for line in lines:
        stripped = line.strip()

        if not stripped.replace('|', '').replace('-', '').replace(':', '').replace(' ', ''):
                continue
            table_buffer.append(stripped)
        else:
            if table_buffer:
                flush_table(table_buffer)
                table_buffer = []
            formatted_text = clean_text_for_pdf(stripped)
            if stripped.startswith('###'):
                clean_heading = stripped.replace('#', '').strip()
                story.append(Paragraph(clean_heading, style_heading))
            elif stripped:
                story.append(Paragraph(formatted_text, style_normal))
    
    if table_buffer: flush_table(table_buffer)
    doc.build(story)
    buffer.seek(0)
    return buffer

# ==========================================
# メイン画面
# ==========================================
st.title("🧶 AIあみぐるみ作家")

FIXED_STYLE = "chibi style, simple round shapes, minimal details, cute, embroidered eyes, thread eyes, small bead eyes, no plastic safety eyes, no giant eyes"

# STEP 1: 画像アップロードと特徴入力
if st.session_state.step == 1:
    st.info("💡 写真からシンプルなあみぐるみのデザインを作成します。")
    
    # 1. ファイルアップローダー
    file_front = st.file_uploader("写真を選択", type=['jpg', 'png', 'webp'])

    # 2. 新しいアップロードがあればセッションを更新
    if file_front:
        st.session_state.input_image = Image.open(file_front)

    # 3. 画像の表示（セッションにある最新の画像を1つだけ表示）
    if st.session_state.input_image:
        st.image(st.session_state.input_image, caption="選択中の画像", width=250)

    # 4. 特徴入力（保持される）
    st.session_state.user_feature = st.text_input(
        "追加の特徴（任意）", 
        value=st.session_state.user_feature,
        placeholder="例：青い帽子をかぶっている、赤いリボン"
    )

    # 5. 生成ボタン（画像があれば表示される）
    if st.session_state.input_image:
        if st.button("デザインを生成する", type="primary"):
            
            # --- 生成処理開始 ---
            with st.spinner("安全性を確認中..."):
                safety_result = check_image_safety(st.session_state.input_image)
                if not safety_result.get("is_safe", False):
                    st.error(f"🚫 公開制限: {safety_result.get('reason', '著作権上の懸念があります')}")
                    st.stop()
            
            with st.spinner("AIがデザイン中..."):
                try:
                    # Geminiに画像の詳細な分析を依頼する（ここが理想に近づけるカギ）
                    prompt_gen_task = f"""
                    Analyze the uploaded image and describe it for an AI image generator.
                    User's specific request: {st.session_state.user_feature}
                    
                    Instructions:
                    - Focus on the main character's color, shape, and unique facial expressions.
                    - Style: Amigurumi (Japanese crochet doll), soft yarn texture, handmade look.
                    - Details: {FIXED_STYLE}
                    - Output only the English prompt for FLUX.
                    """
                    
                    res_prompt = handle_gemini_api_call(
                        client_google.models.generate_content,
                        model=TEXT_MODEL,
                        contents=[prompt_gen_task, st.session_state.input_image]
                    )
                    
                    # 生成されたプロンプトを確認
                    final_prompt = res_prompt.text.strip()
                    
                    # 画像生成 (text_to_imageを使用)
                    generated_image = client_hf.text_to_image(
                        prompt=final_prompt,
                        model="black-forest-labs/FLUX.1-schnell"
                    )
                    
                    img_byte_arr = io.BytesIO()
                    generated_image.save(img_byte_arr, format='PNG')
                    st.session_state.preview_image_bytes = img_byte_arr.getvalue()
                    st.session_state.uploaded_images = [st.session_state.input_image]
                    st.session_state.step = 2
                    st.rerun()

                except Exception as e:
                    st.error(f"画像生成中にエラーが発生しました。しばらく時間をおいてお試しください。")
                    st.debug(f"Error detail: {e}")
    else:
        st.warning("👆 まずは写真をアップロードしてください。")

# STEP 2: 確認
elif st.session_state.step == 2:
    st.subheader("デザイン確認")
    if st.session_state.preview_image_bytes:
        # カラムを使って並べて表示
        col_prev1, col_prev2 = st.columns(2)
        with col_prev1:
            st.image(st.session_state.input_image, caption="元画像", use_container_width=True)
        with col_prev2:
            st.image(st.session_state.preview_image_bytes, caption="完成イメージ", use_container_width=True)
    
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✅ 編み図を作る", type="primary"):
            st.session_state.step = 3
            st.rerun()
    with col2:
        # ❌ やり直す ボタン
        if st.button("❌ やり直す"):
            st.session_state.step = 1
            st.rerun()

# STEP 3: 編み図生成とアフィリエイト (変更なし)
elif st.session_state.step == 3:
    st.subheader("🧶 編み図レシピ")
    
    # --- 👇完成イメージの表示 ---
    if st.session_state.preview_image_bytes:
        # 中央寄せやサイズ調整をしたい場合はカラムを使うと綺麗にまとまります
        col_img1, col_img2, col_img3 = st.columns([1, 2, 1])
        with col_img2:
            st.image(st.session_state.preview_image_bytes, caption="完成イメージ", use_container_width=True)
        st.markdown("---")

    if not st.session_state.pattern_text:
        with st.spinner("編み図を作成中..."):
            prompt_text = f"""
            あみぐるみ作家として、画像のキャラクターの編み図を作成してください。

            【条件】
            - サイズ: {target_size}で、デフォルメされたシンプルな作りにしてください。
            - 目のパーツは大きなプラスチックのさし目は使用せず、刺繍または小さなビーズを指定してください。

            【出力形式の厳守事項】
            1. 各パーツ（頭、体、手足など）ごとの編み図は、必ず以下の「3列のMarkdown表形式」で出力してください。それ以外の列は作らないでください。
            | 段 | 目数 | 編み方・増減 |
            2. 編み方の記号は（細編み、増、減）など、初心者にも分かりやすく記載してください。
            3. テーブル以外の説明（必要な材料、各パーツの組み立て方、仕上げなど）は、表に入れないで通常のテキスト（箇条書き）で書いてください。
            """
            
            # Geminiエラーハンドリングラッパーを使用
            response = handle_gemini_api_call(
                client_google.models.generate_content,
                model=TEXT_MODEL,
                contents=[prompt_text] + st.session_state.uploaded_images
            )
            st.session_state.pattern_text = response.text
            
            color_prompt = "このあみぐるみのメインとなる毛糸の色を1つだけ、日本語の単語で答えてください。（例：赤、水色、白、茶色）余計な説明は不要です。"
            preview_img = Image.open(io.BytesIO(st.session_state.preview_image_bytes))
            
            # Geminiエラーハンドリングラッパーを使用
            color_res = handle_gemini_api_call(
                client_google.models.generate_content,
                model=TEXT_MODEL,
                contents=[color_prompt, preview_img]
            )
            st.session_state.main_yarn_color = color_res.text.strip().replace("\n", "")

    st.markdown(st.session_state.pattern_text)
    
    pdf_file = create_styled_pdf(st.session_state.pattern_text, st.session_state.preview_image_bytes)
    
    st.download_button(
        label="📄 PDFをダウンロード",
        data=pdf_file,
        file_name="amigurumi_recipe.pdf",
        mime="application/pdf"
    )

    st.markdown("---")
    st.subheader("🛍️ おすすめ材料")
    
    # --- キーワードの設定とエンコード ---
    yarn_keyword = f"毛糸 {st.session_state.main_yarn_color}"
    eyes_keyword = "さし目 小"
    
    # 楽天用に日本語キーワードをURLエンコード
    rakuten_yarn_encoded = urllib.parse.quote(yarn_keyword)
    rakuten_eyes_encoded = urllib.parse.quote(eyes_keyword)
    
    # --- Amazonリンク ---
    # スペースを「+」に置き換えてURLが途切れないようにします
    amazon_yarn_link = f"https://www.amazon.co.jp/s?k=毛糸+{st.session_state.main_yarn_color}&tag={AMAZON_TAG}"
    amazon_eyes_link = f"https://www.amazon.co.jp/s?k=さし目+小&tag={AMAZON_TAG}"
    # --- 楽天リンク ---
    # 楽天アフィリエイトの検索結果リンクの基本構造
    rakuten_base = f"https://hb.afl.rakuten.co.jp/hgc/{RAKUTEN_ID}/?pc=https%3A%2F%2Fsearch.rakuten.co.jp%2Fsearch%2Fmall%2F"
    rakuten_yarn_link = f"{rakuten_base}{rakuten_yarn_encoded}%2F"
    rakuten_eyes_link = f"{rakuten_base}{rakuten_eyes_encoded}%2F"
    
    st.markdown(f"今回おすすめの毛糸の色は **{st.session_state.main_yarn_color}** です！")

    # 見やすくカラムで分けて配置
    col_yarn1, col_yarn2 = st.columns(2)
    with col_yarn1:
        st.markdown(f"🧶 **毛糸（{st.session_state.main_yarn_color}）を探す**")
        st.markdown(f"- [🛒 Amazonで探す]({amazon_yarn_link})")
        st.markdown(f"- [🛍️ 楽天市場で探す]({rakuten_yarn_link})")
        
    with col_yarn2:
        st.markdown("👀 **小さなさし目・ビーズを探す**")
        st.markdown(f"- [🛒 Amazonで探す]({amazon_eyes_link})")
        st.markdown(f"- [🛍️ 楽天市場で探す]({rakuten_eyes_link})")
