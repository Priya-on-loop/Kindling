/* =========================================================
   KINDLING — INFERENCE PAGE
   ========================================================= */


/* =========================================================
   SAMPLE DATA
   ========================================================= */

const inferenceData = {
    builds_tinkers: 0.82,
    investigates_why: 0.74,
    creates_expresses: 0.48,
    works_with_people: 0.35,
    organizes_systems: 0.62,
    leads_persuades: 0.42
};


/* =========================================================
   PATTERN DATA
   ========================================================= */

const patterns = [

    {
        number: "01",
        title: "BUILD & TINKER",
        strength: "Showing up often",
        description:
            "You tend to explore by making, testing, changing, and seeing what happens.",
        key: "builds_tinkers"
    },

    {
        number: "02",
        title: "INVESTIGATES WHY",
        strength: "Showing up often",
        description:
            "You often go beyond the first answer and look for the reason behind how something works.",
        key: "investigates_why"
    },

    {
        number: "03",
        title: "CREATE & EXPRESS",
        strength: "Showing up",
        description:
            "Your exploration sometimes moves toward creating, communicating, or expressing an idea.",
        key: "creates_expresses"
    },

    {
        number: "04",
        title: "WORKS WITH PEOPLE",
        strength: "Showing up",
        description:
            "Some of your exploration involves understanding, helping, or collaborating with others.",
        key: "works_with_people"
    },

    {
        number: "05",
        title: "ORGANIZES SYSTEMS",
        strength: "Showing up",
        description:
            "You show interest in bringing structure to information, processes, and connected pieces.",
        key: "organizes_systems"
    },

    {
        number: "06",
        title: "LEADS & PERSUADES",
        strength: "Starting to appear",
        description:
            "Some activities suggest curiosity around influencing ideas, decisions, or direction.",
        key: "leads_persuades"
    }

];


/* =========================================================
   INITIALIZE PAGE
   ========================================================= */

function initializeInference() {

    const canvas =
        document.querySelector("#interestRadar");

    const patternsGrid =
        document.querySelector("#patternsGrid");


    if (!canvas || !patternsGrid) {
        return;
    }


    /* =====================================================
       CREATE PATTERN CARDS
    ===================================================== */

    patternsGrid.innerHTML = "";


    patterns.forEach((pattern) => {

        const card =
            document.createElement("article");

        card.className = "pattern-card";

        card.dataset.pattern =
            pattern.key;


        card.innerHTML = `

            <div class="pattern-card-top">

                <span class="pattern-number">
                    ${pattern.number}
                </span>

                <span class="pattern-strength">
                    ${pattern.strength}
                </span>

            </div>


            <div>

                <h3>
                    ${pattern.title}
                </h3>

                <p>
                    ${pattern.description}
                </p>

            </div>


            <span class="pattern-arrow">
                ↗
            </span>

        `;


        card.addEventListener("click", () => {

            openPatternModal(pattern);

        });


        patternsGrid.appendChild(card);

    });


    /* =====================================================
       DRAW RADAR
    ===================================================== */

    drawRadar(
        canvas,
        inferenceData
    );


    /* =====================================================
       REDRAW ON RESIZE
    ===================================================== */

    let resizeTimer;


    window.addEventListener("resize", () => {

        clearTimeout(resizeTimer);


        resizeTimer = setTimeout(() => {

            drawRadar(
                canvas,
                inferenceData
            );

        }, 100);

    });

}


/* =========================================================
   RADAR DRAWING
   ========================================================= */

function drawRadar(canvas, data) {

    const context =
        canvas.getContext("2d");


    if (!context) {
        return;
    }


    const rect =
        canvas.getBoundingClientRect();


    const devicePixelRatio =
        window.devicePixelRatio || 1;


    canvas.width =
        rect.width * devicePixelRatio;

    canvas.height =
        rect.height * devicePixelRatio;


    context.setTransform(
        devicePixelRatio,
        0,
        0,
        devicePixelRatio,
        0,
        0
    );


    const width =
        rect.width;

    const height =
        rect.height;


    context.clearRect(
        0,
        0,
        width,
        height
    );


    const centerX =
        width / 2;

    const centerY =
        height / 2;


    const radius =
        Math.min(width, height) * 0.34;


    const labels = [

        {
            key: "builds_tinkers",
            label: "BUILD & TINKER"
        },

        {
            key: "investigates_why",
            label: "INVESTIGATES WHY"
        },

        {
            key: "creates_expresses",
            label: "CREATE & EXPRESS"
        },

        {
            key: "works_with_people",
            label: "WORKS WITH PEOPLE"
        },

        {
            key: "organizes_systems",
            label: "ORGANIZES SYSTEMS"
        },

        {
            key: "leads_persuades",
            label: "LEADS & PERSUADES"
        }

    ];


    const sides =
        labels.length;


    /* =====================================================
       GRID
    ===================================================== */

    context.lineWidth = 1;

    context.strokeStyle =
        "#313B47";


    for (
        let level = 1;
        level <= 4;
        level++
    ) {

        const levelRadius =
            radius * (level / 4);


        context.beginPath();


        for (
            let i = 0;
            i < sides;
            i++
        ) {

            const angle =
                -Math.PI / 2 +
                (i * Math.PI * 2 / sides);


            const x =
                centerX +
                levelRadius *
                Math.cos(angle);


            const y =
                centerY +
                levelRadius *
                Math.sin(angle);


            if (i === 0) {

                context.moveTo(x, y);

            } else {

                context.lineTo(x, y);

            }

        }


        context.closePath();

        context.stroke();

    }


    /* =====================================================
       AXES
    ===================================================== */

    labels.forEach((item, index) => {

        const angle =
            -Math.PI / 2 +
            (index * Math.PI * 2 / sides);


        const x =
            centerX +
            radius *
            Math.cos(angle);


        const y =
            centerY +
            radius *
            Math.sin(angle);


        context.beginPath();


        context.moveTo(
            centerX,
            centerY
        );


        context.lineTo(
            x,
            y
        );


        context.stroke();

    });


    /* =====================================================
       DATA POLYGON
    ===================================================== */

    context.beginPath();


    labels.forEach((item, index) => {

        const value =
            data[item.key] || 0;


        const angle =
            -Math.PI / 2 +
            (index * Math.PI * 2 / sides);


        const x =
            centerX +
            radius *
            value *
            Math.cos(angle);


        const y =
            centerY +
            radius *
            value *
            Math.sin(angle);


        if (index === 0) {

            context.moveTo(x, y);

        } else {

            context.lineTo(x, y);

        }

    });


    context.closePath();


    context.fillStyle =
        "rgba(200, 241, 105, 0.12)";

    context.fill();


    context.strokeStyle =
        "#C8F169";

    context.lineWidth = 2;

    context.stroke();


    /* =====================================================
       DATA POINTS
    ===================================================== */

    labels.forEach((item, index) => {

        const value =
            data[item.key] || 0;


        const angle =
            -Math.PI / 2 +
            (index * Math.PI * 2 / sides);


        const x =
            centerX +
            radius *
            value *
            Math.cos(angle);


        const y =
            centerY +
            radius *
            value *
            Math.sin(angle);


        context.beginPath();


        context.arc(
            x,
            y,
            4,
            0,
            Math.PI * 2
        );


        context.fillStyle =
            "#C8F169";

        context.fill();

    });


    /* =====================================================
       LABELS
    ===================================================== */

    context.font =
        "500 11px Inter, sans-serif";

    context.fillStyle =
        "#A8B0BC";

    context.textAlign =
        "center";

    context.textBaseline =
        "middle";


    labels.forEach((item, index) => {

        const angle =
            -Math.PI / 2 +
            (index * Math.PI * 2 / sides);


        const labelRadius =
            radius + 32;


        const x =
            centerX +
            labelRadius *
            Math.cos(angle);


        const y =
            centerY +
            labelRadius *
            Math.sin(angle);


        context.fillText(
            item.label,
            x,
            y
        );

    });

}


/* =========================================================
   PATTERN MODAL
   ========================================================= */

function openPatternModal(pattern) {

    const modal =
        document.querySelector("#patternModal");

    const title =
        document.querySelector("#patternModalTitle");

    const strength =
        document.querySelector("#patternModalStrength");

    const number =
        document.querySelector(".pattern-modal-number");

    const description =
        document.querySelector("#patternModalDescription");


    if (!modal) {
        return;
    }


    if (number) {
        number.textContent =
            pattern.number;
    }


    if (title) {
        title.textContent =
            pattern.title;
    }


    if (strength) {
        strength.textContent =
            pattern.strength;
    }


    if (description) {
        description.textContent =
            pattern.description;
    }


    modal.classList.add("open");

    modal.setAttribute(
        "aria-hidden",
        "false"
    );


    document.body.style.overflow =
        "hidden";

}


function closePatternModal() {

    const modal =
        document.querySelector("#patternModal");


    if (!modal) {
        return;
    }


    modal.classList.remove("open");

    modal.setAttribute(
        "aria-hidden",
        "true"
    );


    document.body.style.overflow =
        "";

}


/* =========================================================
   DOM READY
========================================================= */

document.addEventListener(
    "DOMContentLoaded",
    () => {

        initializeInference();


        const closeButton =
            document.querySelector("#patternModalClose");

        const backdrop =
            document.querySelector("#patternModalBackdrop");

        const acceptButton =
            document.querySelector("#patternAccept");

        const rejectButton =
            document.querySelector("#patternReject");


        closeButton?.addEventListener(
            "click",
            closePatternModal
        );


        backdrop?.addEventListener(
            "click",
            closePatternModal
        );


        acceptButton?.addEventListener(
            "click",
            closePatternModal
        );


        rejectButton?.addEventListener(
            "click",
            closePatternModal
        );


        document.addEventListener(
            "keydown",
            (event) => {

                if (
                    event.key === "Escape"
                ) {

                    closePatternModal();

                }

            }
        );

    }
);