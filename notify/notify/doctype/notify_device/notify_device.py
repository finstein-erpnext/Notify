# Copyright (c) 2026, Finstein and contributors
# For license information, please see license.txt

import hashlib

import frappe
from frappe.model.document import Document


class NotifyDevice(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		enabled: DF.Check
		fcm_token: DF.SmallText
		last_seen: DF.Datetime | None
		platform: DF.Literal["Desktop", "Mobile", "Native"]
		project: DF.Data | None
		token_hash: DF.Data | None
		user: DF.Link
		user_agent: DF.SmallText | None
	# end: auto-generated types

	def before_validate(self):
		if self.fcm_token:
			self.token_hash = hashlib.sha256(self.fcm_token.strip().encode("utf-8")).hexdigest()


def hash_token(token: str) -> str:
	return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()
