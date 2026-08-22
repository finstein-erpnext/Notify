# Copyright (c) 2026, Finstein and contributors
# For license information, please see license.txt

from frappe.model.document import Document


class NotifyRule(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		body_template: DF.SmallText | None
		enabled: DF.Check
		link_template: DF.Data | None
		notify: DF.Literal["All Users With Access", "Users With Specific Roles"]
		reference_doctype: DF.Link
		roles: DF.TableMultiSelect
		rule_name: DF.Data
		sound: DF.Check
		title_template: DF.Data | None
		trigger_event: DF.Literal["New Document", "On Update", "On Submit", "Workflow State Reached"]
		workflow_state: DF.Data | None
	# end: auto-generated types

	def on_update(self):
		# rules changed -> refresh the dispatcher's cached doctype set
		from notify import dispatcher

		dispatcher.clear_rule_cache()

	def on_trash(self):
		from notify import dispatcher

		dispatcher.clear_rule_cache()
