/* =========================================================
   KINDLING — CAREER GRAPH
   ========================================================= */


/* =========================================================
   SAMPLE CAREER DATA
   Temporary frontend data.
   This will later come from the backend.
   ========================================================= */

const careerData = [
    {
        id: "software-developer",
        title: "Software Developer",
        description:
            "Builds and maintains software applications, tools, and systems.",
        family: "Technology",
        x: 50,
        y: 22
    },

    {
        id: "data-scientist",
        title: "Data Scientist",
        description:
            "Uses data, statistics, and programming to investigate problems and uncover patterns.",
        family: "Technology",
        x: 78,
        y: 38
    },

    {
        id: "ux-designer",
        title: "UX Designer",
        description:
            "Explores how people interact with products and designs experiences around their needs.",
        family: "Design",
        x: 76,
        y: 68
    },

    {
        id: "product-manager",
        title: "Product Manager",
        description:
            "Coordinates people, ideas, and priorities to guide the development of products.",
        family: "Product",
        x: 50,
        y: 82
    },

    {
        id: "researcher",
        title: "Researcher",
        description:
            "Investigates questions, gathers evidence, and develops new understanding.",
        family: "Research",
        x: 22,
        y: 68
    },

    {
        id: "systems-analyst",
        title: "Systems Analyst",
        description:
            "Studies systems and processes to identify problems and improve how they work.",
        family: "Technology",
        x: 22,
        y: 38
    }
];


/* =========================================================
   GRAPH STATE
   ========================================================= */

let selectedCareer = null;

let currentScale = 1;

const MIN_SCALE = 0.7;
const MAX_SCALE = 1.6;
const SCALE_STEP = 0.1;


/* =========================================================
   INITIALIZE CAREER GRAPH
   ========================================================= */

function initializeCareerGraph() {

    const graphContainer =
        document.querySelector("#careerGraph");

    if (!graphContainer) {
        console.warn(
            "Kindling: #careerGraph was not found."
        );

        return;
    }


    /*
     * Create the SVG graph.
     */

    createGraph(graphContainer);


    /*
     * Search.
     */

    setupSearch();


    /*
     * Zoom controls.
     */

    setupZoomControls();


    /*
     * Career detail panel.
     */

    setupCareerPanel();


    /*
     * Initial graph render.
     */

    renderGraph();

}


/* =========================================================
   CREATE GRAPH
   ========================================================= */

function createGraph(container) {

    /*
     * Remove any previous SVG.
     */

    const oldSvg =
        container.querySelector("svg");

    if (oldSvg) {
        oldSvg.remove();
    }


    /*
     * Create SVG.
     */

    const svg =
        document.createElementNS(
            "http://www.w3.org/2000/svg",
            "svg"
        );


    svg.setAttribute(
        "class",
        "career-graph-svg"
    );


    svg.setAttribute(
        "viewBox",
        "0 0 1000 700"
    );


    svg.setAttribute(
        "preserveAspectRatio",
        "xMidYMid meet"
    );


    /*
     * Connections layer.
     */

    const connections =
        document.createElementNS(
            "http://www.w3.org/2000/svg",
            "g"
        );


    connections.setAttribute(
        "class",
        "career-graph-connections"
    );


    connections.setAttribute(
        "id",
        "careerConnections"
    );


    /*
     * Nodes layer.
     */

    const nodes =
        document.createElementNS(
            "http://www.w3.org/2000/svg",
            "g"
        );


    nodes.setAttribute(
        "class",
        "career-graph-nodes"
    );


    nodes.setAttribute(
        "id",
        "careerNodes"
    );


    svg.appendChild(connections);

    svg.appendChild(nodes);


    container.appendChild(svg);

}


/* =========================================================
   RENDER GRAPH
   ========================================================= */

function renderGraph() {

    const svg =
        document.querySelector(
            ".career-graph-svg"
        );

    const connections =
        document.querySelector(
            "#careerConnections"
        );

    const nodes =
        document.querySelector(
            "#careerNodes"
        );


    if (!svg || !connections || !nodes) {
        return;
    }


    /*
     * Clear previous content.
     */

    connections.innerHTML = "";

    nodes.innerHTML = "";


    /*
     * Central USER node.
     */

    const centerX = 500;
    const centerY = 350;


    /*
     * Draw connections first so
     * nodes appear above them.
     */

    careerData.forEach((career) => {

        const x =
            career.x * 10;

        const y =
            career.y * 7;


        createConnection(
            connections,
            centerX,
            centerY,
            x,
            y
        );

    });


    /*
     * Create YOU node.
     */

    createUserNode(
        nodes,
        centerX,
        centerY
    );


    /*
     * Create career nodes.
     */

    careerData.forEach((career) => {

        const x =
            career.x * 10;

        const y =
            career.y * 7;


        createCareerNode(
            nodes,
            career,
            x,
            y
        );

    });


    /*
     * Apply current zoom.
     */

    updateGraphScale();

}


/* =========================================================
   CREATE CONNECTION
   ========================================================= */

function createConnection(
    parent,
    x1,
    y1,
    x2,
    y2
) {

    const line =
        document.createElementNS(
            "http://www.w3.org/2000/svg",
            "line"
        );


    line.setAttribute(
        "x1",
        x1
    );

    line.setAttribute(
        "y1",
        y1
    );

    line.setAttribute(
        "x2",
        x2
    );

    line.setAttribute(
        "y2",
        y2
    );


    line.setAttribute(
        "class",
        "career-graph-line"
    );


    parent.appendChild(line);

}


/* =========================================================
   CREATE USER NODE
   ========================================================= */

function createUserNode(
    parent,
    x,
    y
) {

    const group =
        document.createElementNS(
            "http://www.w3.org/2000/svg",
            "g"
        );


    group.setAttribute(
        "class",
        "career-node career-node-user"
    );


    group.setAttribute(
        "transform",
        `translate(${x}, ${y})`
    );


    /*
     * Outer circle.
     */

    const outerCircle =
        document.createElementNS(
            "http://www.w3.org/2000/svg",
            "circle"
        );


    outerCircle.setAttribute(
        "r",
        "48"
    );


    outerCircle.setAttribute(
        "class",
        "career-user-circle"
    );


    /*
     * Inner circle.
     */

    const innerCircle =
        document.createElementNS(
            "http://www.w3.org/2000/svg",
            "circle"
        );


    innerCircle.setAttribute(
        "r",
        "38"
    );


    innerCircle.setAttribute(
        "class",
        "career-user-inner"
    );


    /*
     * YOU text.
     */

    const text =
        document.createElementNS(
            "http://www.w3.org/2000/svg",
            "text"
        );


    text.setAttribute(
        "class",
        "career-user-label"
    );


    text.setAttribute(
        "text-anchor",
        "middle"
    );


    text.setAttribute(
        "dominant-baseline",
        "middle"
    );


    text.textContent =
        "YOU";


    group.appendChild(
        outerCircle
    );

    group.appendChild(
        innerCircle
    );

    group.appendChild(
        text
    );


    parent.appendChild(
        group
    );

}


/* =========================================================
   CREATE CAREER NODE
   ========================================================= */

function createCareerNode(
    parent,
    career,
    x,
    y
) {

    const group =
        document.createElementNS(
            "http://www.w3.org/2000/svg",
            "g"
        );


    group.setAttribute(
        "class",
        "career-node"
    );


    group.setAttribute(
        "data-career-id",
        career.id
    );


    group.setAttribute(
        "transform",
        `translate(${x}, ${y})`
    );


    /*
     * Career circle.
     */

    const circle =
        document.createElementNS(
            "http://www.w3.org/2000/svg",
            "circle"
        );


    circle.setAttribute(
        "r",
        "30"
    );


    circle.setAttribute(
        "class",
        "career-node-circle"
    );


    /*
     * Small center dot.
     */

    const dot =
        document.createElementNS(
            "http://www.w3.org/2000/svg",
            "circle"
        );


    dot.setAttribute(
        "r",
        "5"
    );


    dot.setAttribute(
        "class",
        "career-node-dot"
    );


    /*
     * Career title.
     */

    const title =
        document.createElementNS(
            "http://www.w3.org/2000/svg",
            "text"
        );


    title.setAttribute(
        "class",
        "career-node-title"
    );


    title.setAttribute(
        "text-anchor",
        "middle"
    );


    title.setAttribute(
        "y",
        "52"
    );


    title.textContent =
        career.title;


    /*
     * Career family.
     */

    const family =
        document.createElementNS(
            "http://www.w3.org/2000/svg",
            "text"
        );


    family.setAttribute(
        "class",
        "career-node-family"
    );


    family.setAttribute(
        "text-anchor",
        "middle"
    );


    family.setAttribute(
        "y",
        "69"
    );


    family.textContent =
        career.family;


    group.appendChild(
        circle
    );

    group.appendChild(
        dot
    );

    group.appendChild(
        title
    );

    group.appendChild(
        family
    );


    /*
     * Click interaction.
     */

    group.addEventListener(
        "click",
        () => {

            selectCareer(career);

        }
    );


    parent.appendChild(
        group
    );

}


/* =========================================================
   SELECT CAREER
   ========================================================= */

function selectCareer(career) {

    selectedCareer =
        career;


    /*
     * Highlight selected node.
     */

    document
        .querySelectorAll(
            ".career-node"
        )
        .forEach((node) => {

            node.classList.remove(
                "selected"
            );

        });


    const selectedNode =
        document.querySelector(
            `[data-career-id="${career.id}"]`
        );


    selectedNode?.classList.add(
        "selected"
    );


    /*
     * Open detail panel.
     */

    openCareerPanel(career);

}


/* =========================================================
   CAREER DETAIL PANEL
   ========================================================= */

function openCareerPanel(career) {

    const panel =
        document.querySelector(
            "#careerDetail"
        );


    if (!panel) {
        return;
    }


    const title =
        panel.querySelector(
            "#careerDetailTitle"
        );


    const description =
        panel.querySelector(
            "#careerDetailDescription"
        );


    const family =
        panel.querySelector(
            "#careerDetailFamily"
        );


    if (title) {
        title.textContent =
            career.title;
    }


    if (description) {
        description.textContent =
            career.description;
    }


    if (family) {
        family.textContent =
            career.family;
    }


    panel.classList.add(
        "open"
    );


    panel.setAttribute(
        "aria-hidden",
        "false"
    );

}


/* =========================================================
   CLOSE CAREER PANEL
   ========================================================= */

function closeCareerPanel() {

    const panel =
        document.querySelector(
            "#careerDetail"
        );


    if (!panel) {
        return;
    }


    panel.classList.remove(
        "open"
    );


    panel.setAttribute(
        "aria-hidden",
        "true"
    );


    selectedCareer =
        null;


    document
        .querySelectorAll(
            ".career-node"
        )
        .forEach((node) => {

            node.classList.remove(
                "selected"
            );

        });

}


/* =========================================================
   CAREER PANEL EVENTS
   ========================================================= */

function setupCareerPanel() {

    const closeButton =
        document.querySelector(
            "#careerDetailClose"
        );


    const backdrop =
        document.querySelector(
            "#careerDetailBackdrop"
        );


    closeButton?.addEventListener(
        "click",
        closeCareerPanel
    );


    backdrop?.addEventListener(
        "click",
        closeCareerPanel
    );


    document.addEventListener(
        "keydown",
        (event) => {

            if (
                event.key === "Escape"
            ) {

                closeCareerPanel();

            }

        }
    );

}


/* =========================================================
   SEARCH
   ========================================================= */

function setupSearch() {

    const searchInput =
        document.querySelector(
            "#careerSearch"
        );


    if (!searchInput) {
        return;
    }


    searchInput.addEventListener(
        "input",
        () => {

            const query =
                searchInput.value
                    .trim()
                    .toLowerCase();


            filterCareers(query);

        }
    );


    /*
     * "/" focuses the search box.
     */

    document.addEventListener(
        "keydown",
        (event) => {

            if (
                event.key === "/" &&
                document.activeElement !== searchInput
            ) {

                event.preventDefault();

                searchInput.focus();

            }

        }
    );

}


/* =========================================================
   FILTER CAREERS
   ========================================================= */

function filterCareers(query) {

    document
        .querySelectorAll(
            ".career-node"
        )
        .forEach((node) => {

            /*
             * Keep the YOU node visible.
             */

            if (
                node.classList.contains(
                    "career-node-user"
                )
            ) {

                return;

            }


            const careerId =
                node.dataset.careerId;


            const career =
                careerData.find(
                    (item) =>
                        item.id === careerId
                );


            if (!career) {
                return;
            }


            const searchableText =
                `${career.title} ${career.family} ${career.description}`
                    .toLowerCase();


            const matches =
                searchableText.includes(
                    query
                );


            node.classList.toggle(
                "filtered-out",
                query !== "" && !matches
            );


        });

}


/* =========================================================
   ZOOM CONTROLS
   ========================================================= */

function setupZoomControls() {

    const zoomIn =
        document.querySelector(
            "#zoomIn"
        );


    const zoomOut =
        document.querySelector(
            "#zoomOut"
        );


    const zoomReset =
        document.querySelector(
            "#zoomReset"
        );


    zoomIn?.addEventListener(
        "click",
        () => {

            currentScale =
                Math.min(
                    MAX_SCALE,
                    currentScale + SCALE_STEP
                );


            updateGraphScale();

        }
    );


    zoomOut?.addEventListener(
        "click",
        () => {

            currentScale =
                Math.max(
                    MIN_SCALE,
                    currentScale - SCALE_STEP
                );


            updateGraphScale();

        }
    );


    zoomReset?.addEventListener(
        "click",
        () => {

            currentScale = 1;

            updateGraphScale();

        }
    );

}


/* =========================================================
   UPDATE GRAPH SCALE
   ========================================================= */

function updateGraphScale() {

    const svg =
        document.querySelector(
            ".career-graph-svg"
        );


    if (!svg) {
        return;
    }


    /*
     * Keep the SVG itself stable and
     * scale the internal graph.
     */

    svg.style.transform =
        `scale(${currentScale})`;

}


/* =========================================================
   WINDOW RESIZE
   ========================================================= */

window.addEventListener(
    "resize",
    () => {

        /*
         * The SVG uses a viewBox,
         * so normally no redraw is required.
         *
         * This keeps the function available
         * for future dynamic graph updates.
         */

        updateGraphScale();

    }
);


/* =========================================================
   PAGE INITIALIZATION
   ========================================================= */

document.addEventListener(
    "DOMContentLoaded",
    () => {

        initializeCareerGraph();

    }
);