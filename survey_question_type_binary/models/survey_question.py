# Copyright 2023 Jose Zambudio - Aures Tic <jose@aurestic.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import base64
import binascii
import mimetypes

from odoo import fields, models
from odoo.tools.mimetypes import guess_mimetype
from odoo.tools.misc import formatLang

BINARY_QUESTION_TYPES = ("binary", "multi_binary")
# Upload limit Odoo applies to a request when web.max_file_upload_size is not set
DEFAULT_MAX_REQUEST_SIZE = 128 * 1024 * 1024
# Room kept in a submitted page for what is not a file: tokens, other answers
REQUEST_OVERHEAD = 64 * 1024
MEGABYTE = 1024 * 1024


class SurveyQuestion(models.Model):
    _inherit = "survey.question"

    question_type = fields.Selection(
        selection_add=[
            ("binary", "Binary"),
            ("multi_binary", "Multiple: Binary"),
        ]
    )
    allowed_filemimetypes = fields.Char(
        help="File types accepted, separated by commas: MIME types, groups "
        "of them or extensions (E.g: image/*,application/pdf or .pdf). On a "
        "phone, image types let the participant take a photo or pick one "
        "from the gallery. Leave empty to allow any file.",
    )
    max_filesize = fields.Integer(
        default=50 * MEGABYTE,
        help="Maximum size of each file, in bytes (Default 50MB). Leave empty "
        "to allow any size: a submitted page is still limited by the upload "
        "limit of the server (web.max_file_upload_size).",
    )

    def validate_question(self, answer, comment=None):
        if self.question_type in BINARY_QUESTION_TYPES and answer:
            return self._validate_binary(answer)
        return super().validate_question(answer, comment=comment)

    def _validate_binary(self, answers):
        """Check the files of an answer as the survey form sends them.

        Each file is a dict with its base64 ``data`` and its ``filename``.
        Size and type are measured again from the data: the ones the browser
        sends are not trusted.

        :returns: A dict ``{question.id: error}``, or an empty dict.
        """
        self.ensure_one()
        if not isinstance(answers, list | tuple):
            answers = [answers]
        files = [
            answer
            for answer in answers
            if isinstance(answer, dict) and answer.get("data")
        ]
        if not files:
            if self.constr_mandatory and not self.survey_id.users_can_go_back:
                return {
                    self.id: self.constr_error_msg
                    or self.env._("This question requires an answer.")
                }
            return {}
        if self.question_type == "binary" and len(files) > 1:
            return {self.id: self.env._("Only one file can be sent for this question.")}
        total_size = 0
        for answer in files:
            try:
                content = base64.b64decode(answer["data"], validate=True)
            except (binascii.Error, ValueError, TypeError):
                return {self.id: self.env._("This is not a file")}
            filename = answer.get("filename") or ""
            error = self._get_binary_file_error(
                filename, guess_mimetype(content), len(content)
            )
            if error:
                return {self.id: error}
            total_size += len(content)
        max_request_size = self._get_binary_max_request_size()
        if total_size > max_request_size:
            return {
                self.id: self.env._(
                    "These files weigh %(size)s together; one page can send up "
                    "to %(limit)s. Choose fewer files or smaller ones.",
                    size=self._format_binary_size(total_size),
                    limit=self._format_binary_size(max_request_size),
                )
            }
        return {}

    def _get_binary_file_error(self, filename, mimetype, size, max_size=None):
        """Message for a file this question does not accept, or False.

        :param int max_size: limit to check instead of the one of a submitted
          page (0 for none); saved files are checked against the question only.
        """
        self.ensure_one()
        if max_size is None:
            max_size = self._get_binary_max_file_size()
        if max_size and size > max_size:
            return self.env._(
                "“%(filename)s” weighs %(size)s; the limit is %(limit)s per file.",
                filename=filename,
                size=self._format_binary_size(size),
                limit=self._format_binary_size(max_size),
            )
        if not self._is_binary_type_allowed(mimetype):
            return self.env._(
                "“%(filename)s” is not an accepted file type. Accepted: %(types)s.",
                filename=filename,
                types=", ".join(self._get_binary_allowed_types()),
            )
        return False

    def _get_binary_allowed_types(self):
        """Entries of the allowed types, as written: image/png, image/* or .pdf"""
        self.ensure_one()
        return [
            entry.strip().lower()
            for entry in (self.allowed_filemimetypes or "").split(",")
            if entry.strip()
        ]

    def _is_binary_type_allowed(self, mimetype):
        """Whether a file of the given MIME type, measured from its content, is
        accepted. Extensions are compared through the MIME type they stand for,
        so a file is judged by what it is and not by its name."""
        self.ensure_one()
        allowed = self._get_binary_allowed_types()
        if not allowed:
            return True
        mimetype = (mimetype or "").lower()
        for entry in allowed:
            if entry.startswith("."):
                entry = mimetypes.guess_type(f"file{entry}")[0] or entry
            if entry.endswith("/*"):
                if mimetype.startswith(entry[:-1]):
                    return True
            elif mimetype == entry:
                return True
        return False

    def _get_binary_accept(self):
        """Value of the ``accept`` attribute of the file input: the same list."""
        self.ensure_one()
        return ",".join(self._get_binary_allowed_types())

    def _get_binary_max_request_size(self):
        """Bytes of files one submitted page can carry.

        The page goes to the server in a single request, files in base64 (a
        third more), and the server refuses any request above
        ``web.max_file_upload_size``.
        """
        limit = DEFAULT_MAX_REQUEST_SIZE
        value = (
            self.env["ir.config_parameter"].sudo().get_param("web.max_file_upload_size")
        )
        if value:
            try:
                limit = int(value)
            except ValueError:
                limit = DEFAULT_MAX_REQUEST_SIZE
        return max((limit - REQUEST_OVERHEAD) * 3 // 4, 0)

    def _get_binary_max_file_size(self):
        """Largest file the question accepts: its own limit, if any, and never
        more than what a submitted page can carry."""
        self.ensure_one()
        max_request_size = self._get_binary_max_request_size()
        if self.max_filesize and self.max_filesize > 0:
            return min(self.max_filesize, max_request_size)
        return max_request_size

    def _get_binary_hint(self, has_files=False):
        """Text under the file input: the size limit and, when files are
        already saved, what choosing files again does to them."""
        self.ensure_one()
        hint = self.env._(
            "Up to %(limit)s per file.",
            limit=self._format_binary_size(self._get_binary_max_file_size()),
        )
        if not has_files:
            return hint
        if self.question_type == "multi_binary":
            saved = self.env._(
                "The files above are saved: choose new ones only to replace them."
            )
        else:
            saved = self.env._(
                "The file above is saved: choose another one only to replace it."
            )
        return f"{saved} {hint}"

    def _format_binary_size(self, size):
        """A size for people: megabytes, or kilobytes below one megabyte."""
        if size >= MEGABYTE:
            value = size / MEGABYTE
            digits = 0 if value == int(value) or value >= 100 else 1
            return f"{formatLang(self.env, value, digits=digits)} MB"
        return f"{formatLang(self.env, max(size / 1024, 1), digits=0)} KB"
