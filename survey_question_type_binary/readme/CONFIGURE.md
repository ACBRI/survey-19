Once installed from the configuration of the questions, in the options,
you can indicate the allowed mime types (Allowed Filemimetypes) and the
maximum file size to upload (Max Filesize).

In addition to the binary option, a Multiple: Binary option is supported
which has the same functionality as the single option but allows the
user to add more than one file.

The allowed types are separated by commas and can be MIME types
(`image/png`), groups of them (`image/*`) or extensions (`.pdf`). They
become the `accept` attribute of the file input: with
`image/*,application/pdf`, a phone offers to take a photo, to pick one
from the gallery or to choose a document. The server checks the type
again from the content of each file, not from its name.

The maximum file size applies to each file. A page of the survey is
sent in a single request, so all the files of a page together cannot
exceed the upload limit of the server (the `web.max_file_upload_size`
system parameter, 128 MB by default, of which a quarter goes to the
base64 encoding). The participant sees the limit under the question and
gets a message as soon as a chosen file, or the files of the page
together, go over it. To receive many photos, split them over several
questions or pages.
