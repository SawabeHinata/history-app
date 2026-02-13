import os
import re
from io import BytesIO

import streamlit as st
from dotenv import load_dotenv
from openai import OpenAI
from pypdf import PdfReader


def read_uploaded_files(uploaded_files: list[st.runtime.uploaded_file_manager.UploadedFile]) -> str:
    contents: list[str] = []
    for f in uploaded_files:
        data = f.read()
        ext = os.path.splitext(f.name)[1].lower()
        if ext == ".pdf":
            reader = PdfReader(BytesIO(data))
            pages_text: list[str] = []
            for page in reader.pages:
                pages_text.append(page.extract_text() or "")
            text = "\n".join(pages_text).strip()
            if not text:
                text = "（PDFから文字を抽出できませんでした）"
        else:
            try:
                text = data.decode("utf-8")
            except UnicodeDecodeError:
                text = data.decode("utf-8", errors="replace")
        contents.append(f"--- {f.name} ---\n{text}")
    return "\n\n".join(contents)


def normalize_calendar_terms(text: str) -> str:
    text = re.sub(r"(サッカラージャ|サッカラーヤ|Sakkarāja|Sakkaraja)", "小暦", text)

    def add_western_year(match: re.Match[str]) -> str:
        year = int(match.group(1))
        western = year + 638
        return f"小暦{year}年（西暦{western}年）"

    def fix_existing_western_year(match: re.Match[str]) -> str:
        year = int(match.group(1))
        western = year + 638
        return f"小暦{year}年（西暦{western}年）"

    text = re.sub(r"小暦\s*(\d{1,4})\s*年（西暦\s*\d{1,4}\s*年）", fix_existing_western_year, text)
    text = re.sub(r"小暦\s*(\d{1,4})\s*年(?!（西暦)", add_western_year, text)
    return text


def main() -> None:
    st.set_page_config(page_title="History Assistant", layout="wide")
    st.title("History Assistant")

    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    server_addr = os.getenv("STREAMLIT_SERVER_ADDRESS", "localhost")
    server_port = os.getenv("STREAMLIT_SERVER_PORT", "8501")
    st.caption(f"アクセスURL（推定）: http://{server_addr}:{server_port}")

    st.write("テキストファイル（.txt）またはPDF（.pdf）をアップロードし、質問を入力してください。")

    uploaded_files = st.file_uploader(
        "資料ファイル（複数可）",
        type=["txt", "pdf"],
        accept_multiple_files=True,
    )

    if uploaded_files:
        st.subheader("アップロードされたファイル")
        for f in uploaded_files:
            st.write(f"- {f.name}")

    question = st.text_area("質問", placeholder="例：鎌倉時代の主要な出来事を教えてください。")

    if st.button("送信"):
        if not api_key:
            st.error("OPENAI_API_KEY が .env に設定されていません。")
            return
        if not uploaded_files:
            st.error("少なくとも1つの .txt もしくは .pdf ファイルをアップロードしてください。")
            return
        if not question.strip():
            st.error("質問を入力してください。")
            return

        file_contents = read_uploaded_files(uploaded_files)

        system_prompt = (
            "あなたは提供された資料に基づいて回答する歴史学者のアシスタントです。"
            " 資料に登場する年号と出来事を時系列で整理してください。"
            "資料に書かれていない情報については、その旨を正直に伝えてください。"
            " 出力では「サッカラージャ」「サッカラーヤ」「Sakkarāja」は「小暦」と表記し、"
            "小暦の年は必ず「小暦X年（西暦Y年）」で示してください（西暦Y = 小暦X + 638）。"
        )
        user_prompt = f"以下の資料を参照してください：\n{file_contents}\n\n質問：{question}"

        client = OpenAI(api_key=api_key)

        with st.spinner("回答を生成中..."):
            try:
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                )
            except Exception as exc:
                st.error(f"API呼び出しに失敗しました: {exc}")
                return

        answer = response.choices[0].message.content
        answer = normalize_calendar_terms(answer)
        st.subheader("回答")
        st.write(answer)


if __name__ == "__main__":
    main()
