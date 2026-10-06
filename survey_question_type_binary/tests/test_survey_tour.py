# Copyright 2026 Andrés Camilo Briñez Nuñez (https://github.com/ACBRI)
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo.fields import Command
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestSurveyBinaryTour(HttpCase):
    """The survey form in a browser: files chosen, checked, sent and saved."""

    def test_tour_send_files(self):
        survey = self.env["survey.survey"].create(
            {
                "title": "Company profile",
                "access_mode": "public",
                "users_login_required": False,
                "questions_layout": "one_page",
                "question_and_page_ids": [
                    Command.create(
                        {
                            "title": "Photos of your team",
                            "sequence": 1,
                            "question_type": "multi_binary",
                            "allowed_filemimetypes": "image/*",
                            "max_filesize": 1024 * 1024,
                            "constr_mandatory": True,
                        }
                    ),
                    Command.create(
                        {
                            "title": "Insurance certificate",
                            "sequence": 2,
                            "question_type": "binary",
                            "allowed_filemimetypes": "image/*,application/pdf",
                            "constr_mandatory": True,
                        }
                    ),
                ],
            }
        )
        self.start_tour(
            f"/survey/start/{survey.access_token}", "survey_question_type_binary_tour"
        )
        answer = survey.user_input_ids
        self.assertEqual(answer.state, "done")
        files = answer.user_input_line_ids.answer_binary_ids
        self.assertEqual(
            sorted(files.mapped("filename")),
            ["certificate.pdf", "team.png", "truck.png"],
        )
        self.assertEqual(
            sorted(files.mapped("value_binary_type")),
            ["application/pdf", "image/png", "image/png"],
        )
