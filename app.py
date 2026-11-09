# ==========================================
# KNOWMATE AI - PDF QUESTION ANSWERING CHATBOT
# ==========================================

# 1. IMPORT LIBRARIES

import streamlit as st
import chromadb
import hashlib
import os

from groq import Groq
from pypdf import PdfReader
from sentence_transformers import SentenceTransformer


# ==========================================
# 2. STREAMLIT CONFIGURATION
# ==========================================

st.set_page_config(
    page_title="KnowMate AI",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 KnowMate AI")

st.subheader(
    "Intelligent PDF Question Answering Chatbot"
)

st.write(
    "Upload your PDF documents and ask questions "
    "using Artificial Intelligence."
)

# ==========================================
# GROQ API CONFIGURATION
# ==========================================

def get_groq_api_key():

    try:
        api_key = st.secrets.get("GROQ_API_KEY", "")

    except Exception:
        api_key = os.environ.get("GROQ_API_KEY", "")

    return api_key.strip() if api_key else ""


api_key = get_groq_api_key()

if not api_key:

    st.error("Groq API key is missing.")

    st.stop()


if not api_key.startswith("gsk_"):

    st.error("Invalid Groq API key format.")

    st.stop()


try:

    client = Groq(api_key=api_key)

except Exception as e:

    st.error(f"Groq initialization failed: {e}")

    st.stop()


client = Groq(api_key=api_key)


# ==========================================
# 4. LOAD EMBEDDING MODEL
# ==========================================

@st.cache_resource
def load_embedding_model():

    model = SentenceTransformer(
        "all-MiniLM-L6-v2"
    )

    return model


with st.spinner("Loading embedding model..."):

    embedding_model = load_embedding_model()

# ==========================================
# INITIALIZE CHROMADB
# ==========================================

@st.cache_resource
def initialize_chromadb():

    try:

        chroma_client = chromadb.PersistentClient(
            path="./chroma_db"
        )

        collection = chroma_client.get_or_create_collection(
            name="knowmate_documents",
            metadata={
                "description": "KnowMate AI PDF documents"
            }
        )

        return chroma_client, collection

    except Exception as e:

        st.error(f"ChromaDB initialization failed: {e}")

        st.stop()


chroma_client, collection = initialize_chromadb()

# ==========================================
# 6. EXTRACT TEXT FROM PDF
# ==========================================

def extract_pdf_text(pdf_file):

    reader = PdfReader(pdf_file)

    documents = []

    for page_number, page in enumerate(reader.pages):

        text = page.extract_text()

        if text and text.strip():

            documents.append({

                "text": text,

                "page": page_number + 1

            })

    return documents


# ==========================================
# 7. SPLIT TEXT INTO CHUNKS
# ==========================================

def split_text(text, chunk_size=500, overlap=50):

    words = text.split()

    chunks = []

    step = chunk_size - overlap

    for i in range(0, len(words), step):

        chunk = " ".join(
            words[i:i + chunk_size]
        )

        if chunk.strip():

            chunks.append(chunk)

    return chunks


# ==========================================
# 8. STORE DOCUMENTS IN CHROMADB
# ==========================================

def store_documents(pdf_files):

    documents = []

    metadatas = []

    ids = []

    for pdf_file in pdf_files:

        pages = extract_pdf_text(pdf_file)

        for page_data in pages:

            chunks = split_text(
                page_data["text"]
            )

            for index, chunk in enumerate(chunks):

                documents.append(chunk)

                metadatas.append({

                    "source": pdf_file.name,

                    "page": page_data["page"]

                })

                unique_id = hashlib.md5(

                    f"{pdf_file.name}_{page_data['page']}_{index}".encode()

                ).hexdigest()

                ids.append(unique_id)


    if not documents:

        return 0


    # Generate embeddings

    embeddings = embedding_model.encode(
        documents,
        show_progress_bar=False
    ).tolist()


    # Remove existing records without recreating collection

    existing_ids = collection.get()["ids"]

    if existing_ids:

        collection.delete(
            ids=existing_ids
        )


    # Insert new documents

    collection.add(

        ids=ids,

        documents=documents,

        embeddings=embeddings,

        metadatas=metadatas

    )


    return len(documents)


# ==========================================
# 9. RETRIEVE RELEVANT DOCUMENTS
# ==========================================

def retrieve_documents(question):

    if collection.count() == 0:

        return None

    query_embedding = embedding_model.encode(
        [question]
    ).tolist()


    results = collection.query(

        query_embeddings=query_embedding,

        n_results=min(4, collection.count())

    )

    return results


# ==========================================
# 10. GENERATE ANSWER USING GROQ LLM
# ==========================================

def generate_answer(question, context, history):

    messages = [

        {

            "role": "system",

            "content": """
            You are KnowMate AI, an intelligent PDF
            document question-answering assistant.

            Instructions:

            1. Answer using the provided document context.
            2. Do not invent information.
            3. If the answer is unavailable, clearly say so.
            4. Provide clear and understandable answers.
            5. Use simple language.
            """

        }

    ]


    # Include recent conversation history

    messages.extend(history[-6:])


    messages.append({

        "role": "user",

        "content": f"""

        DOCUMENT CONTEXT:

        {context}


        USER QUESTION:

        {question}


        Provide an answer based on the document context.

        """

    })


    response = client.chat.completions.create(

       model="openai/gpt-oss-120b",

        messages=messages,

        temperature=0.3,

        max_tokens=1000

    )


    return response.choices[0].message.content


# ==========================================
# 11. PDF UPLOAD SECTION
# ==========================================

st.divider()

st.header("📄 Upload Your Documents")


uploaded_files = st.file_uploader(

    "Upload PDF Documents",

    type=["pdf"],

    accept_multiple_files=True

)


if st.button("🚀 Process Documents"):

    if uploaded_files:

        try:

            with st.spinner(
                "Extracting text and generating embeddings..."
            ):

                count = store_documents(
                    uploaded_files
                )


            if count > 0:

                st.success(

                    f"Successfully processed {count} document chunks!"

                )

                st.session_state.messages = []

            else:

                st.warning(
                    "No readable text found in the uploaded PDFs."
                )


        except Exception as e:

            st.error(
                f"Document processing failed: {str(e)}"
            )


    else:

        st.warning(
            "Please upload at least one PDF document."
        )


# ==========================================
# 12. CHAT HISTORY
# ==========================================

if "messages" not in st.session_state:

    st.session_state.messages = []


st.divider()

st.header("💬 Ask Questions About Your Documents")


for message in st.session_state.messages:

    with st.chat_message(message["role"]):

        st.markdown(
            message["content"]
        )


# ==========================================
# 13. USER QUESTION INPUT
# ==========================================

question = st.chat_input(

    "Ask something about your PDF documents..."

)


if question:

    if collection.count() == 0:

        st.warning(
            "Please upload and process PDF documents first."
        )

        st.stop()


    # Display user question

    st.session_state.messages.append({

        "role": "user",

        "content": question

    })


    with st.chat_message("user"):

        st.markdown(question)


    # Generate AI response

    with st.chat_message("assistant"):

        with st.spinner("KnowMate AI is thinking..."):

            try:

                # Retrieve documents

                results = retrieve_documents(
                    question
                )


                retrieved_texts = results["documents"][0]

                metadata = results["metadatas"][0]


                # Combine retrieved context

                context = "\n\n".join(
                    retrieved_texts
                )


                # Generate answer

                answer = generate_answer(

                    question,

                    context,

                    st.session_state.messages[:-1]

                )


                st.markdown(answer)


                # Display sources

                st.markdown("### 📚 Sources")


                for item in metadata:

                    st.write(

                        f"📄 {item['source']} "
                        f"- Page {item['page']}"

                    )


                # Save assistant response

                st.session_state.messages.append({

                    "role": "assistant",

                    "content": answer

                })


            except Exception as e:

                st.error(
                    f"Error generating answer: {str(e)}"
                )
