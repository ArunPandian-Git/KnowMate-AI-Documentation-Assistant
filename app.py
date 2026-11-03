uploaded_files = st.file_uploader(
    "Upload PDF Documents",
    type=["pdf"],
    accept_multiple_files=True
)

if st.button("Process Documents"):

    if uploaded_files:

        with st.spinner("Processing documents..."):

            count = store_documents(
                uploaded_files
            )

        if count > 0:

            st.success(
                f"Successfully processed {count} chunks!"
            )

        else:

            st.warning(
                "No readable text found in the PDFs."
            )

    else:

        st.warning("Please upload PDF documents.")


if "messages" not in st.session_state:

    st.session_state.messages = []


for message in st.session_state.messages:

    with st.chat_message(message["role"]):

        st.markdown(message["content"])


question = st.chat_input(
    "Ask something about your PDF documents..."
)


if question:

    st.session_state.messages.append({
        "role": "user",
        "content": question
    })

    with st.chat_message("user"):

        st.markdown(question)

    with st.chat_message("assistant"):

        with st.spinner("Thinking..."):

            results = collection.query(
                query_embeddings=embedding_model.encode(
                    [question]
                ).tolist(),
                n_results=4
            )

            retrieved_texts = results["documents"][0]

            metadata = results["metadatas"][0]

            context = "\n\n".join(retrieved_texts)

            answer = generate_answer(
                question,
                context,
                st.session_state.messages[:-1]
            )

            st.markdown(answer)

            st.markdown("**Sources:**")

            for item in metadata:

                st.write(
                    f"📄 {item['source']} - "
                    f"Page {item['page']}"
                )

    st.session_state.messages.append({
        "role": "assistant",
        "content": answer
    })


