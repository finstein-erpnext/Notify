# Copyright (c) 2026, Finstein and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class NotifyLog(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		body: DF.SmallText | None
		channel: DF.Literal["Both", "Desktop", "Mobile"]
		devices_count: DF.Int
		error: DF.SmallText | None
		link: DF.Data | None
		reference_doctype: DF.Link | None
		reference_name: DF.DynamicLink | None
		status: DF.Literal["Queued", "Sent", "Skipped", "Failed"]
		title: DF.Data | None
		user: DF.Link | None
	# end: auto-generated types

	pass
