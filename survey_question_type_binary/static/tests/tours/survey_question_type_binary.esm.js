import {registry} from "@web/core/registry";

// A 1x1 transparent PNG
const PNG_BASE64 =
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==";
const PDF_CONTENT = "%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n";

function pngFile(name) {
    const bytes = Uint8Array.from(atob(PNG_BASE64), (char) => char.charCodeAt(0));
    return new File([bytes], name, {type: "image/png"});
}

/**
 * Put files in a file input as if the participant had chosen them.
 *
 * @param {HTMLInputElement} inputEl
 * @param {File[]} files
 */
function chooseFiles(inputEl, files) {
    const dataTransfer = new DataTransfer();
    for (const file of files) {
        dataTransfer.items.add(file);
    }
    inputEl.files = dataTransfer.files;
    inputEl.dispatchEvent(new Event("change", {bubbles: true}));
}

const TEAM = 'div.js_question-wrapper:contains("Photos of your team")';
const CERTIFICATE = 'div.js_question-wrapper:contains("Insurance certificate")';

registry.category("web_tour.tours").add("survey_question_type_binary_tour", {
    steps: () => [
        {
            content: "Start the survey",
            trigger: 'button.btn-primary:contains("Start Survey")',
            run: "click",
        },
        {
            content: "Choose a photo heavier than the limit of the question",
            trigger: `${TEAM} input.o_survey_question_binary`,
            run() {
                chooseFiles(this.anchor, [
                    new File([new Uint8Array(1024 * 1024 + 1)], "too-big.png", {
                        type: "image/png",
                    }),
                ]);
            },
        },
        {
            content: "The limit is explained and the photo is not kept",
            trigger: `${TEAM} .o_survey_question_error:contains("the limit is 1 MB per file")`,
            run() {
                const inputEl = document.querySelector(
                    ".o_survey_question_binary[data-question-type='multi_binary']"
                );
                if (inputEl.files.length) {
                    throw new Error("The file over the limit is still in the input");
                }
            },
        },
        {
            content: "Choose two photos",
            trigger: `${TEAM} input.o_survey_question_binary`,
            run() {
                chooseFiles(this.anchor, [pngFile("team.png"), pngFile("truck.png")]);
            },
        },
        {
            content: "Both photos are listed under the question, without the error",
            trigger: `${TEAM} .o_survey_binary_selection li:contains("truck.png")`,
            run() {
                const errorEl = document.querySelector(
                    `.js_question-wrapper:has([data-question-type='multi_binary']) > .o_survey_question_error`
                );
                if (errorEl.textContent.trim()) {
                    throw new Error(`An error is still shown: ${errorEl.textContent}`);
                }
            },
        },
        {
            content: "Choose the insurance certificate",
            trigger: `${CERTIFICATE} input.o_survey_question_binary`,
            run() {
                chooseFiles(this.anchor, [
                    new File([PDF_CONTENT], "certificate.pdf", {
                        type: "application/pdf",
                    }),
                ]);
            },
        },
        {
            content: "Submit the survey",
            trigger: 'button[value="finish"]',
            run: "click",
        },
        {
            content: "Confirm",
            trigger: ".modal-footer button.btn-primary",
            run: "click",
        },
        {
            content: "The answers are saved",
            trigger: 'h1:contains("Thank you!")',
        },
    ],
});
