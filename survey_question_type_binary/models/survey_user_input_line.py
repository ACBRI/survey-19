# Copyright 2023 Jose Zambudio - Aures Tic <jose@aurestic.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import api, fields, models
from odoo.exceptions import ValidationError

from .survey_question import BINARY_QUESTION_TYPES


class SurveyUserInputLine(models.Model):
    _inherit = "survey.user_input.line"

    answer_type = fields.Selection(
        selection_add=[
            ("binary", "Binary"),
            ("multi_binary", "Multi: Binary"),
        ]
    )
    answer_binary_ids = fields.One2many(
        comodel_name="survey.user_input.line_binary",
        inverse_name="input_line_id",
        string="Files",
        readonly=True,
        # A copied participation keeps its files: without them, its binary
        # lines would not pass _check_answer_type_skipped.
        copy=True,
    )

    @api.constrains("skipped", "answer_type")
    def _check_answer_type_skipped(self):
        binary_lines = self.filtered(
            lambda line: line.answer_type in BINARY_QUESTION_TYPES
        )
        for line in binary_lines:
            if line.skipped:
                raise ValidationError(
                    self.env._(
                        "A question can either be skipped or answered, not both."
                    )
                )
            if not line.answer_binary_ids:
                raise ValidationError(
                    self.env._("The answer must be in the right type")
                )
        return super(
            SurveyUserInputLine, self - binary_lines
        )._check_answer_type_skipped()

    @api.constrains("question_id", "answer_type", "answer_binary_ids")
    def _check_binary_answer(self):
        for line in self:
            if line.answer_type not in BINARY_QUESTION_TYPES:
                continue
            for file in line.answer_binary_ids:
                error = line.question_id._get_binary_file_error(
                    file.filename,
                    file.value_binary_type,
                    file.value_binary_size,
                    max_size=max(line.question_id.max_filesize, 0),
                )
                if error:
                    raise ValidationError(error)

    @api.depends("answer_binary_ids.filename")
    def _compute_display_name(self):
        res = super()._compute_display_name()
        for line in self:
            if line.answer_type not in BINARY_QUESTION_TYPES:
                continue
            if len(line.answer_binary_ids) == 1:
                line.display_name = line.answer_binary_ids.filename
            elif line.answer_binary_ids:
                line.display_name = self.env._(
                    "%(count)s files", count=len(line.answer_binary_ids)
                )
        return res

    def unlink(self):
        # The files would go with their line through a database cascade, which
        # leaves their attachments behind: they are deleted by the ORM first.
        self.sudo().answer_binary_ids.unlink()
        return super().unlink()
