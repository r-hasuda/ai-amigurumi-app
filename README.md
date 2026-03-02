
![Uploading screencapture-localhost-8501-2026-03-01-14_22_34.png…]()


🧶 AIあみぐるみ作家 (AI Amigurumi Artist)
「写真から、あなただけのあみぐるみレシピを。」

アップロードした写真をもとに、AIが可愛くデフォルメされたデザインを生成し、初心者でも編める詳細な編み図（レシピ）を作成するアプリです。

🌟 主な機能

AIデザイン生成: アップロードされた写真の特徴を捉え、FLUX（画像生成AI）を用いて「あみぐるみ化」した完成予想図を提案します。

詳細な編み図（レシピ）作成: Gemini 2.5 Flashを活用し、頭・体・手足などのパーツごとに、段数・目数・編み方を表形式で出力します。

PDFレシピダウンロード: 作成した編み図は、完成予想図付きのPDFとしてダウンロードし、オフラインでも確認可能です。

材料レコメンド機能: レシピに最適な毛糸の色やパーツを判定し、Amazonや楽天市場からすぐに購入できるリンクを表示します。

著作権・安全性チェック: 公開制限のあるキャラクターや人物が含まれていないか、AIが事前に安全性を確認します。

🛠 技術スタック
Frontend: Streamlit

AI Models:

Google Gemini 2.5 Flash (画像解析 & テキスト生成)

Hugging Face / FLUX.1-schnell (画像生成)

PDF Generation: ReportLab (IPAexGothicフォント対応)

Infrastructure: Streamlit Community Cloud

📋 要件定義・仕様
1. ターゲットユーザー
あみぐるみ作りを手軽に楽しみたい初心者。

オリジナルのデザインを形にしたいクリエイター。

ペットや思い出の品をあみぐるみにしたい方。

2. デザインコンセプト

仕上がりサイズ: 手のひらサイズで丸みを帯びたデフォルメ体型を基本とします。

3. レシピ構成要素
生成される編み図には以下の情報が含まれます：

使用する道具と毛糸の色リスト 。

パーツ別編み図（頭、体、手足、耳、しっぽ等）。

組み立てと仕上げのガイド（わたの詰め方、パーツの接続位置など）。

🚀 セットアップと実行
リポジトリをクローンまたはダウンロードします。

必要なライブラリをインストールします：

Bash
pip install -r requirements.txt
.env ファイルにAPIキーを設定するか、Streamlit CloudのSecretsに登録します：

GOOGLE_API_KEY

HUGGINGFACE_API_KEY

アプリを起動します：

Bash
streamlit run app_amigurumi.py
