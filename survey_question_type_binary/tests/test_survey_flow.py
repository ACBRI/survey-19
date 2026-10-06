# Copyright 2026 Andrés Camilo Briñez Nuñez (https://github.com/ACBRI)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import base64

from odoo.tests import HttpCase, tagged
from odoo.tools import file_open

from odoo.addons.survey.tests import common

PDF_CONTENT = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


@tagged("post_install", "-at_install")
class TestSurveyBinaryFlow(common.TestSurveyCommon, HttpCase):
    """A participant sends files through the routes the survey form uses."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with file_open(
            "survey_question_type_binary/static/description/icon.png", "rb"
        ) as img:
            cls.image_content = img.read()
        cls.image_base64 = base64.b64encode(cls.image_content).decode()
        cls.pdf_base64 = base64.b64encode(PDF_CONTENT).decode()
        Question = cls.env["survey.question"].with_user(cls.survey_manager)
        cls.binary_survey = (
            cls.env["survey.survey"]
            .with_user(cls.survey_manager)
            .create(
                {
                    "title": "Company profile",
                    "access_mode": "public",
                    "users_login_required": False,
                    "users_can_go_back": True,
                    "questions_layout": "page_per_section",
                }
            )
        )
        cls.page_files = Question.create(
            {
                "is_page": True,
                "question_type": False,
                "sequence": 1,
                "title": "Your files",
                "survey_id": cls.binary_survey.id,
            }
        )
        cls.question_photos = Question.create(
            {
                "title": "Photos of your team",
                "sequence": 2,
                "question_type": "multi_binary",
                "allowed_filemimetypes": "image/*",
                "max_filesize": 10 * 1024 * 1024,
                "constr_mandatory": True,
                "survey_id": cls.binary_survey.id,
            }
        )
        cls.question_certificate = Question.create(
            {
                "title": "Insurance certificate",
                "sequence": 3,
                "question_type": "binary",
                "allowed_filemimetypes": "image/*,application/pdf",
                "survey_id": cls.binary_survey.id,
            }
        )
        cls.page_contact = Question.create(
            {
                "is_page": True,
                "question_type": False,
                "sequence": 4,
                "title": "Contact",
                "survey_id": cls.binary_survey.id,
            }
        )
        cls.question_name = Question.create(
            {
                "title": "Your name",
                "sequence": 5,
                "question_type": "char_box",
                "survey_id": cls.binary_survey.id,
            }
        )

    def _file(self, data, filename, mimetype):
        return {"data": data, "filename": filename, "size": 0, "type": mimetype}

    def _start(self):
        survey = self.binary_survey
        self.assertResponse(self._access_start(survey), 200)
        answer = self.env["survey.user_input"].search([("survey_id", "=", survey.id)])
        response = self._access_page(survey, answer.access_token)
        csrf_token = self._find_csrf_token(response.text)
        self.assertResponse(self._access_begin(survey, answer.access_token), 200)
        return answer, answer.access_token, csrf_token

    def _submit(self, answer_token, csrf_token, page, values, **extra):
        post_data = dict(
            values, page_id=page.id, csrf_token=csrf_token, token=answer_token, **extra
        )
        response = self._access_submit(self.binary_survey, answer_token, post_data)
        self.assertResponse(response, 200)
        return response.json()["result"]

    def _file_url(self, answer_token, file):
        return (
            f"/survey/binary/{self.binary_survey.access_token}/{answer_token}/{file.id}"
        )

    def test_01_files_go_from_the_form_to_the_answer(self):
        answer, answer_token, csrf_token = self._start()

        # The page offers the camera or the gallery, and says the limit
        page_html = self._access_page(self.binary_survey, answer_token).text
        self.assertIn('accept="image/*"', page_html)
        self.assertIn('accept="image/*,application/pdf"', page_html)
        self.assertIn('multiple="multiple"', page_html)
        self.assertIn("Up to 10 MB per file.", page_html)

        result = self._submit(
            answer_token,
            csrf_token,
            self.page_files,
            {
                str(self.question_photos.id): [
                    self._file(self.image_base64, "team.png", "image/png"),
                    self._file(self.image_base64, "truck.png", "image/png"),
                ],
                str(self.question_certificate.id): [
                    self._file(self.pdf_base64, "certificate.pdf", "application/pdf")
                ],
            },
        )
        self.assertNotIn("error", result[1])
        answer.invalidate_recordset()
        lines = answer.user_input_line_ids
        photos = lines.filtered(lambda line: line.question_id == self.question_photos)
        certificate = lines.filtered(
            lambda line: line.question_id == self.question_certificate
        )
        self.assertEqual(photos.answer_type, "multi_binary")
        self.assertEqual(
            photos.answer_binary_ids.mapped("filename"), ["team.png", "truck.png"]
        )
        self.assertEqual(certificate.answer_type, "binary")
        self.assertEqual(
            certificate.answer_binary_ids.value_binary_type, "application/pdf"
        )
        attachment = (
            self.env["ir.attachment"]
            .sudo()
            .search(
                [
                    ("res_model", "=", "survey.user_input.line_binary"),
                    ("res_field", "=", "value_binary"),
                    ("res_id", "=", certificate.answer_binary_ids.id),
                ]
            )
        )
        self.assertEqual(attachment.raw, PDF_CONTENT)

        # The participant reaches the files with the tokens of the answer
        team = photos.answer_binary_ids[0]
        response = self.url_open(self._file_url(answer_token, team))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, self.image_content)
        self.assertEqual(response.headers["Content-Type"], "image/png")
        response = self.url_open(self._file_url(answer_token, team) + "?thumbnail=1")
        self.assertEqual(response.status_code, 200)
        response = self.url_open(
            self._file_url(answer_token, certificate.answer_binary_ids)
        )
        self.assertEqual(response.content, PDF_CONTENT)
        self.assertIn("attachment", response.headers["Content-Disposition"])
        # Nobody else does
        self.assertEqual(
            self.url_open(self._file_url("wrong-token", team)).status_code, 404
        )
        self.assertResponse(self._access_start(self.binary_survey), 200)
        other_answer = self.env["survey.user_input"].search(
            [("survey_id", "=", self.binary_survey.id), ("id", "!=", answer.id)]
        )
        self.assertEqual(
            self.url_open(self._file_url(other_answer.access_token, team)).status_code,
            404,
        )

        # Back on the page: the saved files are shown and kept when the page is
        # submitted again without choosing new ones
        result = self._submit(
            answer_token,
            csrf_token,
            self.page_contact,
            {str(self.question_name.id): "Ana"},
            previous_page_id=self.page_files.id,
        )
        self.assertIn("team.png", result[1]["survey_content"])
        self.assertIn(
            "The files above are saved: choose new ones only to replace them.",
            result[1]["survey_content"],
        )
        self.assertIn(self._file_url(answer_token, team), result[1]["survey_content"])
        result = self._submit(answer_token, csrf_token, self.page_files, {})
        self.assertNotIn("error", result[1])
        self.env.invalidate_all()
        self.assertEqual(
            photos.answer_binary_ids.mapped("filename"), ["team.png", "truck.png"]
        )
        result = self._submit(
            answer_token,
            csrf_token,
            self.page_contact,
            {str(self.question_name.id): "Ana"},
        )
        answer.invalidate_recordset()
        self.assertEqual(answer.state, "done")

        # The printed answers list the files
        response = self.url_open(
            f"/survey/print/{self.binary_survey.access_token}"
            f"?answer_token={answer_token}"
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("certificate.pdf", response.text)
        self.assertIn(self._file_url(answer_token, team), response.text)

        # And so do the results of the survey, for its officers
        self.authenticate(self.survey_manager.login, self.survey_manager.login)
        response = self.url_open(f"/survey/results/{self.binary_survey.id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("truck.png", response.text)
        self.assertIn(
            f"/web/content/survey.user_input.line_binary/{team.id}/value_binary",
            response.text,
        )

    def test_02_files_are_checked_on_the_server(self):
        # Mandatory answers are checked page by page when going back is not allowed
        self.binary_survey.users_can_go_back = False
        answer, answer_token, csrf_token = self._start()
        # A mandatory question without files
        result = self._submit(answer_token, csrf_token, self.page_files, {})
        self.assertEqual(result[1]["error"], "validation")
        self.assertIn(str(self.question_photos.id), result[1]["fields"])
        # A file that is not what the question accepts, whatever its name says
        result = self._submit(
            answer_token,
            csrf_token,
            self.page_files,
            {
                str(self.question_photos.id): [
                    self._file(self.pdf_base64, "photo.png", "image/png")
                ],
            },
        )
        self.assertEqual(
            result[1]["fields"][str(self.question_photos.id)],
            "“photo.png” is not an accepted file type. Accepted: image/*.",
        )
        answer.invalidate_recordset()
        self.assertFalse(
            answer.user_input_line_ids.filtered(
                lambda line: line.question_id == self.question_photos
            )
        )
