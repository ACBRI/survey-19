# Copyright 2023 Jose Zambudio - Aures Tic <jose@aurestic.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import models
from odoo.exceptions import UserError
from odoo.fields import Command

from .survey_question import BINARY_QUESTION_TYPES


class SurveyUserInput(models.Model):
    _inherit = "survey.user_input"

    def _save_lines(self, question, answer, comment=None, overwrite_existing=True):
        """Save the files of a binary question in a single answer line.

        Files sent again replace the ones saved before. Nothing sent keeps
        the line as it is: a file input cannot be filled in advance, so a
        participant who comes back to a page and submits it without choosing
        files again still has the files of the first time.
        """
        if question.question_type not in BINARY_QUESTION_TYPES:
            return super()._save_lines(
                question, answer, comment=comment, overwrite_existing=overwrite_existing
            )
        old_answers = self.env["survey.user_input.line"].search(
            [
                ("user_input_id", "=", self.id),
                ("question_id", "=", question.id),
            ]
        )
        vals = self._get_line_answer_values(question, answer, question.question_type)
        if not vals.get("answer_binary_ids") and old_answers:
            return old_answers
        if old_answers and not overwrite_existing:
            raise UserError(self.env._("This answer cannot be overwritten."))
        # Files are kept as they were sent: Odoo would otherwise shrink the
        # photos to 1920 pixels when it stores them as attachments.
        lines = self.env["survey.user_input.line"].with_context(
            image_no_postprocess=True
        )
        if old_answers:
            # A binary question keeps a single line per participation
            old_answers[1:].unlink()
            old_answers = old_answers[:1]
            vals["answer_binary_ids"] = [Command.clear()] + vals.get(
                "answer_binary_ids", []
            )
            old_answers.with_env(lines.env).write(vals)
            return old_answers
        return lines.create(vals)

    def _get_line_answer_values(self, question, answer, answer_type):
        if answer_type not in BINARY_QUESTION_TYPES:
            return super()._get_line_answer_values(question, answer, answer_type)
        # Without files, the values of a skipped line
        vals = super()._get_line_answer_values(question, False, answer_type)
        if not isinstance(answer, list | tuple):
            answer = [answer]
        files = [file for file in answer if isinstance(file, dict) and file.get("data")]
        if files:
            vals.update(
                skipped=False,
                answer_type=answer_type,
                answer_binary_ids=[
                    Command.create(
                        {
                            "value_binary": file["data"],
                            "filename": file.get("filename") or "file",
                        }
                    )
                    for file in files
                ],
            )
        return vals

    def unlink(self):
        # The answer lines go with their participation through a database
        # cascade, which would leave the attachments of their files behind.
        self.sudo().user_input_line_ids.answer_binary_ids.unlink()
        return super().unlink()
