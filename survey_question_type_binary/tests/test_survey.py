# Copyright 2023 Jose Zambudio - Aures Tic <jose@aurestic.es>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import base64
import io

from PIL import Image

from odoo.exceptions import AccessError, ValidationError
from odoo.fields import Command
from odoo.tools import file_open, mute_logger

from odoo.addons.mail.tests.common import mail_new_test_user
from odoo.addons.survey.tests import common

PDF_CONTENT = b"%PDF-1.4\n1 0 obj\n<<>>\nendobj\ntrailer\n<<>>\n%%EOF\n"


class TestSurvey(common.SurveyCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.survey_manager = mail_new_test_user(
            cls.env,
            name="Maria Riera",
            login="Riera",
            email="maria.riera@example.com",
            groups="survey.group_survey_manager,base.group_user",
        )
        cls.survey_user = mail_new_test_user(
            cls.env,
            name="Lukas Peeters",
            login="survey_binary_user",
            email="survey.user@example.com",
            groups="survey.group_survey_user,base.group_user",
        )
        cls.user_emp = mail_new_test_user(
            cls.env,
            name="Eglantine Employee",
            login="survey_binary_employee",
            email="employee@example.com",
            groups="base.group_user",
        )
        cls.survey1 = (
            cls.env["survey.survey"]
            .with_user(cls.survey_manager)
            .create({"title": "S0", "page_ids": [(0, 0, {"title": "P0"})]})
        )
        cls.page1 = (
            cls.env["survey.question"]
            .with_user(cls.survey_manager)
            .create(
                {
                    "title": "First page",
                    "survey_id": cls.survey1.id,
                    "sequence": 1,
                    "is_page": True,
                }
            )
        )
        cls.user_input1 = (
            cls.env["survey.user_input"]
            .with_user(cls.survey_manager)
            .create(
                {
                    "survey_id": cls.survey1.id,
                    "partner_id": cls.survey_manager.partner_id.id,
                }
            )
        )
        cls.question_binary = (
            cls.env["survey.question"]
            .with_user(cls.survey_manager)
            .create(
                {
                    "title": "Test Binary",
                    "page_id": cls.page1.id,
                    "survey_id": cls.survey1.id,
                    "question_type": "binary",
                    "allowed_filemimetypes": "application/pdf",
                    "max_filesize": 1024,
                    "constr_mandatory": True,
                    "validation_required": True,
                }
            )
        )
        cls.question_multi_binary = (
            cls.env["survey.question"]
            .with_user(cls.survey_manager)
            .create(
                {
                    "title": "Test Binary",
                    "page_id": cls.page1.id,
                    "survey_id": cls.survey1.id,
                    "question_type": "multi_binary",
                    "allowed_filemimetypes": "image/png",
                    "max_filesize": 2097152,
                    "validation_required": True,
                }
            )
        )
        with file_open(
            "survey_question_type_binary/static/description/icon.png", "rb"
        ) as img:
            cls.image_content = img.read()
        cls.image_base64 = base64.b64encode(cls.image_content)
        cls.pdf_base64 = base64.b64encode(PDF_CONTENT)

    def _binary_line(self, question, user_input=None):
        user_input = user_input or self.user_input1
        return user_input.user_input_line_ids.filtered(
            lambda line: line.question_id == question
        )

    def test_01_question_binary_with_error_values(self):
        required = "This question requires an answer."
        self.assertEqual(
            self.question_binary.validate_question({}),
            {self.question_binary.id: required},
        )
        self.assertEqual(
            self.question_binary.validate_question({"data": b""}),
            {self.question_binary.id: required},
        )
        self.assertEqual(
            self.question_binary.validate_question({"data": "This is not a file"}),
            {self.question_binary.id: "This is not a file"},
        )
        self.assertEqual(
            self.question_binary.validate_question(
                {"data": self.image_base64, "filename": "icon.png"}
            ),
            {
                self.question_binary.id: "“icon.png” weighs 9 KB; "
                "the limit is 1 KB per file."
            },
        )
        self.question_binary.max_filesize = 2097152  # Increse to 2.0MB
        self.assertEqual(
            self.question_binary.validate_question(
                {"data": self.image_base64, "filename": "icon.png"}
            ),
            {
                self.question_binary.id: "“icon.png” is not an accepted file type. "
                "Accepted: application/pdf."
            },
        )

    def test_02_question_binary_with_valid_values(self):
        self.question_binary.max_filesize = 2097152  # Increse to 2.0MB
        self.question_binary.allowed_filemimetypes = "image/png"
        self.assertEqual(
            self.question_binary.validate_question({"data": self.image_base64}),
            {},
        )
        self.user_input1._save_lines(
            question=self.question_binary,
            answer={
                "data": self.image_base64,
                "filename": "test image.png",
            },
        )
        self.assertTrue(self._binary_line(self.question_binary).answer_binary_ids)

    def test_03_question_multi_binary_with_valid_values(self):
        self.assertEqual(
            self.question_multi_binary.validate_question(
                [
                    {"data": self.image_base64},
                    {"data": self.image_base64},
                    {"data": self.image_base64},
                    {"data": self.image_base64},
                ]
            ),
            {},
        )

    def test_04_question_binary_data(self):
        self.user_input1._save_lines(
            question=self.question_multi_binary,
            answer=[
                {
                    "data": self.image_base64,
                    "filename": "test image.png",
                }
            ],
        )
        answer = self._binary_line(self.question_multi_binary).answer_binary_ids
        self.assertTrue(
            answer.is_binary_image,
        )
        self.assertEqual(answer.value_binary_type, "image/png")
        self.assertEqual(answer.value_binary_size, 9455)
        self.assertEqual(answer.display_name, "test image.png")

    def test_05_allowed_types(self):
        question = self.question_binary
        question.max_filesize = 2097152
        image = {"data": self.image_base64, "filename": "icon.png"}
        pdf = {"data": self.pdf_base64, "filename": "certificate.pdf"}
        # Groups of types and extensions, judged by the content of the file
        question.allowed_filemimetypes = "image/*, application/pdf"
        self.assertEqual(question.validate_question(image), {})
        self.assertEqual(question.validate_question(pdf), {})
        self.assertEqual(question._get_binary_accept(), "image/*,application/pdf")
        question.allowed_filemimetypes = ".pdf"
        self.assertEqual(question.validate_question(pdf), {})
        self.assertIn(question.id, question.validate_question(image))
        renamed_image = dict(image, filename="icon.pdf")
        self.assertIn(question.id, question.validate_question(renamed_image))
        question.allowed_filemimetypes = False
        self.assertEqual(question.validate_question(image), {})
        self.assertEqual(question._get_binary_accept(), "")

    def test_06_single_binary_takes_one_file(self):
        self.question_binary.write(
            {"max_filesize": 2097152, "allowed_filemimetypes": "image/png"}
        )
        file = {"data": self.image_base64, "filename": "icon.png"}
        self.assertEqual(
            self.question_binary.validate_question([file, file]),
            {self.question_binary.id: "Only one file can be sent for this question."},
        )

    def test_07_limit_of_a_submitted_page(self):
        question = self.question_multi_binary
        # 128 MiB by default, minus the room for the rest of the page, in base64
        self.assertEqual(
            question._get_binary_max_request_size(),
            (128 * 1024 * 1024 - 64 * 1024) * 3 // 4,
        )
        self.assertEqual(question._get_binary_max_file_size(), 2097152)
        self.assertEqual(question._get_binary_hint(), "Up to 2 MB per file.")
        # A server that takes 96 KiB per request carries 24 KiB of files
        self.env["ir.config_parameter"].sudo().set_param(
            "web.max_file_upload_size", str(96 * 1024)
        )
        self.assertEqual(question._get_binary_max_request_size(), 24 * 1024)
        self.assertEqual(question._get_binary_max_file_size(), 24 * 1024)
        file = {"data": self.image_base64, "filename": "icon.png"}
        self.assertEqual(question.validate_question([file, file]), {})
        self.assertEqual(
            question.validate_question([file, file, file]),
            {
                question.id: "These files weigh 28 KB together; one page can "
                "send up to 24 KB. Choose fewer files or smaller ones."
            },
        )
        question.max_filesize = 0
        self.assertEqual(question._get_binary_max_file_size(), 24 * 1024)
        self.assertEqual(
            question._get_binary_hint(has_files=True),
            "The files above are saved: choose new ones only to replace them. "
            "Up to 24 KB per file.",
        )

    def test_08_files_are_attachments(self):
        self.user_input1._save_lines(
            self.question_multi_binary,
            [
                {"data": self.image_base64, "filename": "team.png"},
                {"data": self.image_base64, "filename": "truck.png"},
            ],
        )
        line = self._binary_line(self.question_multi_binary)
        self.assertRecordValues(
            line, [{"answer_type": "multi_binary", "skipped": False}]
        )
        self.assertEqual(line.display_name, "2 files")
        files = line.answer_binary_ids
        self.assertEqual(files.mapped("filename"), ["team.png", "truck.png"])
        attachments = (
            self.env["ir.attachment"]
            .sudo()
            .search(
                [
                    ("res_model", "=", "survey.user_input.line_binary"),
                    ("res_field", "=", "value_binary"),
                    ("res_id", "in", files.ids),
                ]
            )
        )
        self.assertEqual(len(attachments), 2)
        for attachment in attachments:
            self.assertEqual(attachment.raw, self.image_content)
            self.assertEqual(attachment.mimetype, "image/png")

    def test_09_files_sent_again_replace_the_saved_ones(self):
        question = self.question_multi_binary
        self.user_input1._save_lines(
            question, [{"data": self.image_base64, "filename": "first.png"}]
        )
        line = self._binary_line(question)
        first_file = line.answer_binary_ids
        self.user_input1._save_lines(
            question,
            [
                {"data": self.image_base64, "filename": "second.png"},
                {"data": self.image_base64, "filename": "third.png"},
            ],
        )
        self.assertEqual(self._binary_line(question), line)
        self.assertEqual(
            line.answer_binary_ids.mapped("filename"), ["second.png", "third.png"]
        )
        self.assertFalse(first_file.exists())
        self.assertFalse(
            self.env["ir.attachment"]
            .sudo()
            .search_count(
                [
                    ("res_model", "=", "survey.user_input.line_binary"),
                    ("res_field", "=", "value_binary"),
                    ("res_id", "=", first_file.id),
                ]
            )
        )

    def test_10_nothing_sent_keeps_the_saved_files(self):
        question = self.question_multi_binary
        self.user_input1._save_lines(
            question, [{"data": self.image_base64, "filename": "kept.png"}]
        )
        self.user_input1._save_lines(question, [])
        line = self._binary_line(question)
        self.assertFalse(line.skipped)
        self.assertEqual(line.answer_binary_ids.filename, "kept.png")

    def test_11_nothing_sent_without_saved_files_is_skipped(self):
        self.user_input1._save_lines(self.question_multi_binary, [])
        line = self._binary_line(self.question_multi_binary)
        self.assertRecordValues(line, [{"skipped": True, "answer_type": False}])
        self.assertEqual(line.display_name, "Skipped")

    def test_12_binary_line_needs_files(self):
        with self.assertRaises(ValidationError), mute_logger("odoo.sql_db"):
            self.env["survey.user_input.line"].create(
                {
                    "user_input_id": self.user_input1.id,
                    "question_id": self.question_multi_binary.id,
                    "answer_type": "multi_binary",
                    "skipped": False,
                }
            )

    def test_13_saved_files_follow_the_question_rules(self):
        self.question_binary.max_filesize = 2097152
        with self.assertRaises(ValidationError):
            self.env["survey.user_input.line"].create(
                {
                    "user_input_id": self.user_input1.id,
                    "question_id": self.question_binary.id,
                    "answer_type": "binary",
                    "answer_binary_ids": [
                        Command.create(
                            {"value_binary": self.image_base64, "filename": "icon.png"}
                        )
                    ],
                }
            )

    def test_14_deleted_answers_take_their_attachments(self):
        self.user_input1._save_lines(
            self.question_multi_binary,
            [{"data": self.image_base64, "filename": "team.png"}],
        )
        files = self._binary_line(self.question_multi_binary).answer_binary_ids
        domain = [
            ("res_model", "=", "survey.user_input.line_binary"),
            ("res_field", "=", "value_binary"),
            ("res_id", "in", files.ids),
        ]
        Attachment = self.env["ir.attachment"].sudo()
        self.assertEqual(Attachment.search_count(domain), 1)
        self.user_input1.unlink()
        self.assertFalse(files.exists())
        self.assertEqual(Attachment.search_count(domain), 0)

    def test_15_cascades_leave_no_orphan_attachment(self):
        self.user_input1._save_lines(
            self.question_multi_binary,
            [{"data": self.image_base64, "filename": "team.png"}],
        )
        file = self._binary_line(self.question_multi_binary).answer_binary_ids
        attachment = (
            self.env["ir.attachment"]
            .sudo()
            .search(
                [
                    ("res_model", "=", "survey.user_input.line_binary"),
                    ("res_field", "=", "value_binary"),
                    ("res_id", "=", file.id),
                ]
            )
        )
        self.assertTrue(attachment)
        # Deleting the question removes the file through database cascades
        self.question_multi_binary.unlink()
        self.assertFalse(file.exists())
        self.assertTrue(attachment.exists())
        self.env["survey.user_input.line_binary"]._gc_orphan_attachments()
        self.assertFalse(attachment.exists())

    def test_16_access_to_the_files(self):
        self.user_input1._save_lines(
            self.question_multi_binary,
            [{"data": self.image_base64, "filename": "team.png"}],
        )
        file = self._binary_line(self.question_multi_binary).answer_binary_ids
        self.assertEqual(file.with_user(self.survey_user).filename, "team.png")
        self.assertTrue(file.with_user(self.survey_manager).value_binary)
        with self.assertRaises(AccessError):
            file.with_user(self.user_emp).read(["filename"])
        # An officer outside the users of a restricted survey does not see them
        self.survey1.restrict_user_ids = self.survey_manager.ids
        file.invalidate_recordset()
        with self.assertRaises(AccessError):
            file.with_user(self.survey_user).read(["filename"])

    def test_17_copied_participation_keeps_its_files(self):
        self.user_input1._save_lines(
            self.question_multi_binary,
            [{"data": self.image_base64, "filename": "team.png"}],
        )
        copy = self.user_input1.copy()
        line = self._binary_line(self.question_multi_binary, copy)
        self.assertEqual(line.answer_binary_ids.filename, "team.png")
        self.assertNotEqual(
            line.answer_binary_ids,
            self._binary_line(self.question_multi_binary).answer_binary_ids,
        )

    def test_18_files_are_stored_as_sent(self):
        """A photo wider than 1920 pixels is not shrunk on its way to the
        filestore, as Odoo does with other image attachments."""
        buffer = io.BytesIO()
        Image.new("RGB", (2400, 16), (40, 90, 140)).save(buffer, format="PNG")
        photo = buffer.getvalue()
        self.user_input1._save_lines(
            self.question_multi_binary,
            [{"data": base64.b64encode(photo), "filename": "wide.png"}],
        )
        file = self._binary_line(self.question_multi_binary).answer_binary_ids
        attachment = (
            self.env["ir.attachment"]
            .sudo()
            .search(
                [
                    ("res_model", "=", "survey.user_input.line_binary"),
                    ("res_field", "=", "value_binary"),
                    ("res_id", "=", file.id),
                ]
            )
        )
        self.assertEqual(attachment.raw, photo)
        self.assertEqual(file.value_binary_size, len(photo))

    def test_19_messages_of_the_form_are_translated(self):
        """The public pages load the JavaScript translations of this module."""
        self.assertIn(
            "survey_question_type_binary",
            self.env["ir.http"]._get_translation_frontend_modules_name(),
        )
