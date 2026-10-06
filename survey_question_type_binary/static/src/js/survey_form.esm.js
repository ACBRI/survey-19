import {SurveyForm} from "@survey/interactions/survey_form";
import {_t} from "@web/core/l10n/translation";
import {formatFloat} from "@web/core/utils/numbers";
import {patch} from "@web/core/utils/patch";
import {patchDynamicContent} from "@web/public/utils";

const MEGABYTE = 1024 * 1024;

/**
 * A size for people: megabytes, or kilobytes below one megabyte, with the
 * decimal mark of the participant's language.
 *
 * @param {Number} size in bytes
 * @returns {String}
 */
export function formatBinarySize(size) {
    if (size >= MEGABYTE) {
        const megabytes = size / MEGABYTE;
        const digits = Number.isInteger(megabytes) || megabytes >= 100 ? 0 : 1;
        return `${formatFloat(megabytes, {digits: [0, digits]})} MB`;
    }
    return `${formatFloat(Math.max(size / 1024, 1), {digits: [0, 0]})} KB`;
}

/**
 * Whether a file matches the ``accept`` attribute of its input: MIME types,
 * groups of them (image/*) or extensions (.pdf). The server checks the type
 * again from the content; this only spares the participant a useless upload.
 *
 * @param {File} file
 * @param {String} accept
 * @returns {Boolean}
 */
export function isFileAccepted(file, accept) {
    const entries = (accept || "")
        .split(",")
        .map((entry) => entry.trim().toLowerCase())
        .filter(Boolean);
    const type = (file.type || "").toLowerCase();
    if (!entries.length || !type) {
        return true;
    }
    const name = file.name.toLowerCase();
    return entries.some((entry) => {
        if (entry.startsWith(".")) {
            return name.endsWith(entry);
        }
        if (entry.endsWith("/*")) {
            return type.startsWith(entry.slice(0, -1));
        }
        return type === entry;
    });
}

patch(SurveyForm.prototype, {
    setup() {
        super.setup();
        // Files read from the inputs of the page, by question, while it is submitted
        this.binaryAnswers = {};
        patchDynamicContent(this.dynamicContent, {
            ".o_survey_question_binary": {
                "t-on-change": this.onBinaryInputChange.bind(this),
            },
        });
    },

    /**
     * Check the files as soon as they are chosen. A file the question does
     * not take empties the input, with the reason under the question: the
     * participant learns it now, not after waiting for the whole upload.
     *
     * @param {Event} ev
     */
    onBinaryInputChange(ev) {
        const inputEl = ev.currentTarget;
        const error = this.getBinaryInputError(inputEl);
        if (error) {
            inputEl.value = "";
            this.showErrors({[inputEl.name]: error});
        } else {
            this.clearBinaryError(inputEl.name);
        }
        this.renderBinarySelection(inputEl);
    },

    /**
     * @param {HTMLInputElement} inputEl
     * @returns {String} why the files chosen in the input cannot be sent, or ""
     */
    getBinaryInputError(inputEl) {
        const files = [...inputEl.files];
        const maxFileSize = Number(inputEl.dataset.maxFileSize) || 0;
        for (const file of files) {
            if (!isFileAccepted(file, inputEl.accept)) {
                return _t("“%(filename)s” is not an accepted file type.", {
                    filename: file.name,
                });
            }
            if (maxFileSize && file.size > maxFileSize) {
                return _t(
                    "“%(filename)s” weighs %(size)s; the limit is %(limit)s per file.",
                    {
                        filename: file.name,
                        size: formatBinarySize(file.size),
                        limit: formatBinarySize(maxFileSize),
                    }
                );
            }
        }
        // The page is sent in a single request, with the files of all its questions
        const maxUploadSize = Number(inputEl.dataset.maxUploadSize) || 0;
        const totalSize = [...this.el.querySelectorAll(".o_survey_question_binary")]
            .flatMap((el) => [...el.files])
            .reduce((total, file) => total + file.size, 0);
        if (files.length && maxUploadSize && totalSize > maxUploadSize) {
            return _t(
                "These files weigh %(size)s together; one page can send up to %(limit)s. Choose fewer files or smaller ones.",
                {
                    size: formatBinarySize(totalSize),
                    limit: formatBinarySize(maxUploadSize),
                }
            );
        }
        return "";
    },

    /**
     * @param {String} questionId
     */
    clearBinaryError(questionId) {
        const errorEl = this.el.querySelector(
            `.js_question-wrapper[id="${questionId}"] > .o_survey_question_error`
        );
        if (errorEl) {
            errorEl.replaceChildren();
            errorEl.classList.remove("slide_in");
        }
    },

    /**
     * List the chosen files with their size under the input: on a phone, the
     * input itself only says how many there are.
     *
     * @param {HTMLInputElement} inputEl
     */
    renderBinarySelection(inputEl) {
        const listEl = inputEl.parentElement.querySelector(
            ".o_survey_binary_selection"
        );
        if (!listEl) {
            return;
        }
        listEl.replaceChildren(
            ...[...inputEl.files].map((file) => {
                const itemEl = document.createElement("li");
                itemEl.textContent = `${file.name} (${formatBinarySize(file.size)})`;
                return itemEl;
            })
        );
    },

    validateForm(formEl, formData) {
        const isValid = super.validateForm(formEl, formData);
        const errors = {};
        const inactiveQuestionIds = this.options.sessionInProgress
            ? []
            : this.getInactiveConditionalQuestionIds();
        for (const inputEl of formEl.querySelectorAll(".o_survey_question_binary")) {
            const questionWrapperEl = inputEl.closest(".js_question-wrapper");
            if (inactiveQuestionIds.includes(parseInt(questionWrapperEl.id, 10))) {
                continue;
            }
            const error = this.getBinaryInputError(inputEl);
            if (error) {
                errors[questionWrapperEl.id] = error;
            } else if (
                questionWrapperEl.hasAttribute("data-required") &&
                !inputEl.files.length &&
                !inputEl.dataset.hasAnswer
            ) {
                errors[questionWrapperEl.id] =
                    questionWrapperEl.dataset.constrErrorMsg ||
                    _t("This question requires an answer.");
            }
        }
        if (Object.keys(errors).length) {
            this.showErrors(errors);
            return false;
        }
        return isValid;
    },

    /**
     * Read the chosen files before the page is submitted: the survey sends a
     * page as JSON, so each file travels in base64 with its name.
     *
     * @param {Object} [options] see SurveyForm.submitForm
     */
    async submitForm(options = {}) {
        if (this.submitting || this.options.isStartScreen) {
            return super.submitForm(options);
        }
        let binaryAnswers = {};
        try {
            binaryAnswers = await this.waitFor(this.readBinaryAnswers());
        } catch (error) {
            if (!error.binaryQuestionId) {
                throw error;
            }
            this.showErrors({
                [error.binaryQuestionId]: _t(
                    "“%(filename)s” could not be read. Choose it again.",
                    {filename: error.binaryFilename}
                ),
            });
            return;
        }
        this.binaryAnswers = binaryAnswers;
        try {
            return await super.submitForm(options);
        } finally {
            this.binaryAnswers = {};
        }
    },

    /**
     * @returns {Promise<Object>} the files of each binary question of the page:
     *   {questionId: [{data, filename, size, type}]}
     */
    async readBinaryAnswers() {
        const answers = {};
        const inputEls = [...this.el.querySelectorAll(".o_survey_question_binary")];
        await Promise.all(
            inputEls
                .filter((inputEl) => inputEl.files.length)
                .map(async (inputEl) => {
                    answers[inputEl.name] = await Promise.all(
                        [...inputEl.files].map((file) =>
                            this.readBinaryFile(file, inputEl.name)
                        )
                    );
                })
        );
        return answers;
    },

    /**
     * @param {File} file
     * @param {String} questionId
     * @returns {Promise<Object>}
     */
    readBinaryFile(file, questionId) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
                resolve({
                    // A data URL: "data:<type>;base64,<data>"
                    data: reader.result.split(",")[1] || "",
                    filename: file.name,
                    size: file.size,
                    type: file.type,
                });
            };
            reader.onerror = () => {
                const error = new Error(reader.error?.message || "FileReader error");
                error.binaryQuestionId = questionId;
                error.binaryFilename = file.name;
                reject(error);
            };
            reader.readAsDataURL(file);
        });
    },

    prepareSubmitValues(formData, params) {
        super.prepareSubmitValues(formData, params);
        for (const [questionId, files] of Object.entries(this.binaryAnswers)) {
            params[questionId] = files;
        }
    },
});
