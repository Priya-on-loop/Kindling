/* =========================================================
   SIGNALS PAGE
   ========================================================= */

function initializeSignals() {

    const welcome = document.querySelector("#signalsWelcome");
    const chatContainer = document.querySelector("#chatContainer");
    const chatMessages = document.querySelector("#chatMessages");
    const chatForm = document.querySelector("#chatForm");
    const chatInput = document.querySelector("#chatInput");
    const chatSend = document.querySelector("#chatSend");
    const chatLoading = document.querySelector("#chatLoading");
    const questionProgress = document.querySelector("#questionProgress");

    if (
        !welcome ||
        !chatContainer ||
        !chatMessages ||
        !chatForm ||
        !chatInput
    ) {
        return;
    }


    /* =====================================================
       API CONFIGURATION
       ===================================================== */

    /*
     * Change this URL when your FastAPI backend
     * is running somewhere else.
     *
     * Example:
     *
     * const API_BASE_URL = "http://127.0.0.1:8000";
     */

    const API_BASE_URL = "http://127.0.0.1:8000";


    /* =====================================================
       STATE
       ===================================================== */

    let sessionId = null;

    let questionIndex = 1;

    let totalQuestions = 5;

    let isLoading = false;

    let conversationStarted = false;


    /* =====================================================
       ADD MESSAGE
       ===================================================== */

    function addMessage(message, type) {

        const messageElement =
            document.createElement("div");

        messageElement.className =
            `chat-message ${type}`;


        const contentElement =
            document.createElement("div");

        contentElement.className =
            "chat-message-content";


        contentElement.textContent = message;


        messageElement.appendChild(
            contentElement
        );


        chatMessages.appendChild(
            messageElement
        );


        scrollToLatestMessage();

    }


    /* =====================================================
       SCROLL
       ===================================================== */

    function scrollToLatestMessage() {

        requestAnimationFrame(() => {

            window.scrollTo({
                top: document.body.scrollHeight,
                behavior: "smooth"
            });

        });

    }


    /* =====================================================
       LOADING
       ===================================================== */

    function setLoading(loading) {

        isLoading = loading;


        if (chatLoading) {

            chatLoading.classList.toggle(
                "visible",
                loading
            );

        }


        if (chatSend) {

            chatSend.disabled = loading;

        }


        chatInput.disabled = loading;

    }


    /* =====================================================
       PROGRESS
       ===================================================== */

    function updateProgress() {

        questionProgress.textContent =
            `Question ${questionIndex} of ${totalQuestions}`;

    }


    /* =====================================================
       START CHAT
       ===================================================== */

    async function startConversation() {

        setLoading(true);


        try {

            const response = await fetch(
                `${API_BASE_URL}/api/chat/start`,
                {
                    method: "POST",

                    headers: {
                        "Content-Type": "application/json"
                    },

                    body: JSON.stringify({})
                }
            );


            if (!response.ok) {

                throw new Error(
                    `Server returned ${response.status}`
                );

            }


            const data =
                await response.json();


            /*
             * Expected response:
             *
             * {
             *   "session_id": "...",
             *   "opening_question": "..."
             * }
             */


            sessionId =
                data.session_id;


            if (!sessionId) {

                throw new Error(
                    "No session ID received."
                );

            }


            /*
             * Put the backend's opening question
             * into our existing welcome screen.
             */

            const openingQuestion =
                document.querySelector(
                    "#openingQuestion"
                );


            if (openingQuestion &&
                data.opening_question) {

                openingQuestion.textContent =
                    data.opening_question;

            }


            updateProgress();

        }

        catch (error) {

            console.error(
                "Failed to start chat:",
                error
            );


            showError(
                "We couldn't start the conversation. Please try again."
            );

        }

        finally {

            setLoading(false);

        }

    }


    /* =====================================================
       SEND MESSAGE
       ===================================================== */

    async function sendMessage(message) {

        if (
            !message ||
            isLoading ||
            !sessionId
        ) {
            return;
        }


        /*
         * The welcome screen disappears
         * when the user sends their first message.
         */

        if (!conversationStarted) {

            conversationStarted = true;

            welcome.classList.add("hidden");

            chatContainer.classList.add("active");

        }


        addMessage(
            message,
            "user"
        );


        chatInput.value = "";

        chatInput.style.height = "auto";


        setLoading(true);


        try {

            const response = await fetch(
                `${API_BASE_URL}/api/chat/message`,
                {
                    method: "POST",

                    headers: {
                        "Content-Type": "application/json"
                    },

                    body: JSON.stringify({

                        session_id: sessionId,

                        message: message

                    })
                }
            );


            if (!response.ok) {

                throw new Error(
                    `Server returned ${response.status}`
                );

            }


            const data =
                await response.json();


            /*
             * Expected response:
             *
             * {
             *   "reply": "...",
             *   "question_index": 2,
             *   "total_questions": 5
             * }
             */


            if (data.reply) {

                addMessage(
                    data.reply,
                    "ai"
                );

            }


            if (
                typeof data.question_index ===
                "number"
            ) {

                questionIndex =
                    data.question_index;

            }


            if (
                typeof data.total_questions ===
                "number"
            ) {

                totalQuestions =
                    data.total_questions;

            }


            updateProgress();

        }

        catch (error) {

            console.error(
                "Failed to send message:",
                error
            );


            showError(
                "We couldn't send your response. Please try again."
            );

        }

        finally {

            setLoading(false);

            chatInput.focus();

        }

    }


    /* =====================================================
       ERROR
       ===================================================== */

    function showError(message) {

        /*
         * Remove an existing error first.
         */

        const existingError =
            document.querySelector(
                ".chat-error"
            );


        if (existingError) {

            existingError.remove();

        }


        const errorElement =
            document.createElement("div");

        errorElement.className =
            "chat-error";

        errorElement.textContent =
            message;


        chatForm.appendChild(
            errorElement
        );

    }


    /* =====================================================
       FORM SUBMIT
       ===================================================== */

    chatForm.addEventListener(
        "submit",
        (event) => {

            event.preventDefault();


            const message =
                chatInput.value.trim();


            if (!message) {

                return;

            }


            sendMessage(message);

        }
    );


    /* =====================================================
       TEXTAREA AUTO RESIZE
       ===================================================== */

    chatInput.addEventListener(
        "input",
        () => {

            chatInput.style.height =
                "auto";


            chatInput.style.height =
                `${Math.min(
                    chatInput.scrollHeight,
                    150
                )}px`;

        }
    );


    /* =====================================================
       ENTER TO SEND
       ===================================================== */

    chatInput.addEventListener(
        "keydown",
        (event) => {

            if (
                event.key === "Enter" &&
                !event.shiftKey
            ) {

                event.preventDefault();

                chatForm.requestSubmit();

            }

        }
    );


    /* =====================================================
       INITIAL STATE
       ===================================================== */

    updateProgress();

    startConversation();

}