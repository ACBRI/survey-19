# Copyright 2023 Jose Zambudio - Aures Tic <jose@aurestic.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import base64

from odoo import api, fields, models
from odoo.tools import SQL
from odoo.tools.mimetypes import guess_mimetype

VALID_MIMETYPES = [
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/bmp",
    "image/webp",
    "image/svg+xml",
    "image/x-icon",
]


class SurveyUserInputLineBinary(models.Model):
    _name = "survey.user_input.line_binary"
    _description = "Survey User Input Line Binary"
    _rec_name = "filename"

    input_line_id = fields.Many2one(
        comodel_name="survey.user_input.line",
        required=True,
        readonly=True,
        index=True,
        ondelete="cascade",
    )
    # Stored as an attachment of this record, in the filestore
    value_binary = fields.Binary(
        string="File",
        required=True,
        readonly=True,
    )
    filename = fields.Char(
        required=True,
        readonly=True,
    )
    value_binary_type = fields.Char(
        string="Type",
        compute="_compute_binary_data",
        store=True,
        readonly=True,
    )
    value_binary_size = fields.Integer(
        string="Size (bytes)",
        compute="_compute_binary_data",
        store=True,
        readonly=True,
    )
    value_binary_size_display = fields.Char(
        string="Size",
        compute="_compute_value_binary_size_display",
    )
    is_binary_image = fields.Boolean(
        string="Image",
        compute="_compute_binary_data",
        store=True,
        readonly=True,
    )

    @api.depends("value_binary")
    def _compute_binary_data(self):
        for line in self.with_context(bin_size=False):
            content = base64.b64decode(line.value_binary or b"")
            line.value_binary_type = guess_mimetype(content)
            line.value_binary_size = len(content)
            line.is_binary_image = line.value_binary_type in VALID_MIMETYPES

    @api.depends("value_binary_size")
    def _compute_value_binary_size_display(self):
        question = self.env["survey.question"]
        for line in self:
            line.value_binary_size_display = question._format_binary_size(
                line.value_binary_size
            )

    @api.autovacuum
    def _gc_orphan_attachments(self):
        """Delete the attachments of files that no longer exist.

        Deleting a survey, a question or a participation removes its answer
        files through database cascades, which leave their attachments, and
        the files in the filestore, behind.
        """
        self.env.cr.execute(
            SQL(
                """
                SELECT attachment.id
                  FROM ir_attachment attachment
                 WHERE attachment.res_model = %(model)s
                   AND NOT EXISTS (
                       SELECT 1 FROM %(table)s binary_file
                        WHERE binary_file.id = attachment.res_id
                   )
                """,
                model=self._name,
                table=SQL.identifier(self._table),
            )
        )
        orphan_ids = [row[0] for row in self.env.cr.fetchall()]
        self.env["ir.attachment"].sudo().browse(orphan_ids).unlink()
