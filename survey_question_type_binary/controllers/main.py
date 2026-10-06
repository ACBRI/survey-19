# Copyright 2026 Andrés Camilo Briñez Nuñez (https://github.com/ACBRI)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from werkzeug.exceptions import NotFound

from odoo import http
from odoo.http import request

from odoo.addons.survey.controllers.main import Survey

THUMBNAIL_SIZE = 256


class SurveyBinary(Survey):
    @http.route(
        "/survey/binary/<string:survey_token>/<string:answer_token>/<int:file_id>",
        type="http",
        auth="public",
        website=True,
        sitemap=False,
    )
    def survey_binary_file(
        self, survey_token, answer_token, file_id, thumbnail=None, download=None, **kw
    ):
        """A file of an answer, for whoever holds the tokens of that answer.

        The participant and the survey officers reach the files through the
        same tokens as the printed answers (``/survey/print``): the files are
        stored with no access for public users.
        """
        access_data = self._get_access_data(
            survey_token, answer_token, ensure_token=True, check_partner=False
        )
        validity_code = access_data["validity_code"]
        if validity_code is not True and not (
            access_data["has_survey_access"]
            and validity_code in ("survey_closed", "survey_void", "answer_deadline")
        ):
            raise NotFound()
        file_sudo = (
            request.env["survey.user_input.line_binary"].sudo().browse(file_id).exists()
        )
        if (
            not file_sudo
            or file_sudo.input_line_id.user_input_id != access_data["answer_sudo"]
        ):
            raise NotFound()
        binary = request.env["ir.binary"]
        is_raster_image = (
            file_sudo.is_binary_image and file_sudo.value_binary_type != "image/svg+xml"
        )
        if thumbnail and is_raster_image:
            stream = binary._get_image_stream_from(
                file_sudo,
                "value_binary",
                filename_field="filename",
                width=THUMBNAIL_SIZE,
                height=THUMBNAIL_SIZE,
            )
        else:
            stream = binary._get_stream_from(
                file_sudo, "value_binary", filename_field="filename"
            )
        # Images open in the browser; anything else is downloaded
        return stream.get_response(
            as_attachment=bool(download) or not file_sudo.is_binary_image
        )
