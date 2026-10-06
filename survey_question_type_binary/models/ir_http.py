# Copyright 2026 Andrés Camilo Briñez Nuñez (https://github.com/ACBRI)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import models


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @classmethod
    def _get_translation_frontend_modules_name(cls):
        # The messages of the survey form about files are written in its
        # JavaScript: the public pages load them only for the modules listed here.
        mods = super()._get_translation_frontend_modules_name()
        return mods + ["survey_question_type_binary"]
