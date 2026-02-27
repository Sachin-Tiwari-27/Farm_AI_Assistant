import os
import logging
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton
from telegram.ext import (
    ContextTypes, ConversationHandler,
    CommandHandler, CallbackQueryHandler
)

import database as db

load_dotenv()
logger = logging.getLogger(__name__)

# --- ACCESS CONTROL ---
# Parse comma-separated list from env; falls back to empty set (no admins) if unset.
_raw_ids = os.getenv("ADMIN_USER_IDS", "")
ADMIN_IDS: set[int] = {
    int(uid.strip()) for uid in _raw_ids.split(",") if uid.strip().isdigit()
}

def is_admin(update: Update) -> bool:
    return update.effective_user.id in ADMIN_IDS

# --- STATES ---
ADMIN_LIST, ADMIN_CONFIRM_DELETE = range(2)

# ------------------------------------------------------------------ #
# HELPERS
# ------------------------------------------------------------------ #

def _build_user_list_message(users: list) -> tuple[str, InlineKeyboardMarkup]:
    """Build the admin panel message and keyboard from a users summary list."""
    if not users:
        text = "👤 **Admin Panel**\n\n_No registered users found._"
        kb = [[InlineKeyboardButton("🔄 Refresh", callback_data="admin_refresh")],
              [InlineKeyboardButton("❌ Close", callback_data="admin_close")]]
    else:
        text = f"👤 **Admin Panel** — {len(users)} registered user(s)\n\n"
        for u in users:
            text += f"• `{u['id']}` — **{u['name']}** ({u['farm']}, {u['landmark_count']} spot(s))\n"
        text += "\nTap a user to manage them:"
        kb = []
        for u in users:
            kb.append([InlineKeyboardButton(
                f"🗑 {u['name']} ({u['farm']})",
                callback_data=f"admin_del_{u['id']}"
            )])
        kb.append([
            InlineKeyboardButton("🔄 Refresh", callback_data="admin_refresh"),
            InlineKeyboardButton("❌ Close", callback_data="admin_close")
        ])

    return text, InlineKeyboardMarkup(kb)


def _cancel_user_jobs(application, user_id: int):
    """Remove all scheduled JobQueue jobs that belong to this user."""
    uid_str = str(user_id)
    removed = 0
    for job in application.job_queue.jobs():
        if uid_str in job.name:
            job.schedule_removal()
            removed += 1
    if removed:
        logger.info(f"Admin: cancelled {removed} job(s) for deleted user {user_id}.")


# ------------------------------------------------------------------ #
# ENTRY POINT
# ------------------------------------------------------------------ #

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """/admin — Show the admin user management panel."""
    if not is_admin(update):
        return ConversationHandler.END   # Silently ignore non-admins

    users = db.get_all_users_summary()
    text, kb = _build_user_list_message(users)

    await update.message.reply_text(text, reply_markup=kb, parse_mode='Markdown')
    return ADMIN_LIST


# ------------------------------------------------------------------ #
# STATE: ADMIN_LIST
# ------------------------------------------------------------------ #

async def handle_admin_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles button presses on the main admin panel."""
    if not is_admin(update):
        return ConversationHandler.END

    query = update.callback_query
    await query.answer()
    action = query.data

    if action == "admin_close":
        await query.edit_message_text("🔒 Admin panel closed.")
        return ConversationHandler.END

    if action == "admin_refresh":
        users = db.get_all_users_summary()
        text, kb = _build_user_list_message(users)
        await query.edit_message_text(text, reply_markup=kb, parse_mode='Markdown')
        return ADMIN_LIST

    if action.startswith("admin_del_"):
        target_id_str = action.split("admin_del_")[1]
        if not target_id_str.isdigit():
            await query.edit_message_text("❌ Invalid user ID.")
            return ADMIN_LIST

        target_id = int(target_id_str)
        # Find user name for confirmation prompt
        users = db.get_all_users_summary()
        target = next((u for u in users if u['id'] == target_id), None)

        if not target:
            await query.edit_message_text("⚠️ User not found. They may have already been removed.")
            return ConversationHandler.END

        context.user_data['admin_target_id'] = target_id
        context.user_data['admin_target_name'] = target['name']

        confirm_text = (
            f"⚠️ **Confirm Deletion**\n\n"
            f"You are about to permanently remove:\n"
            f"👤 **{target['name']}** — _{target['farm']}_\n"
            f"🪨 {target['landmark_count']} landmark(s) will also be deleted.\n\n"
            f"_Logs are preserved._\n\n"
            f"**This cannot be undone. Are you sure?**"
        )
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Yes, Delete", callback_data="admin_confirm_yes")],
            [InlineKeyboardButton("❌ Cancel", callback_data="admin_confirm_no")]
        ])
        await query.edit_message_text(confirm_text, reply_markup=kb, parse_mode='Markdown')
        return ADMIN_CONFIRM_DELETE

    return ADMIN_LIST


# ------------------------------------------------------------------ #
# STATE: ADMIN_CONFIRM_DELETE
# ------------------------------------------------------------------ #

async def handle_confirm_delete(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the Yes/No confirmation for user deletion."""
    if not is_admin(update):
        return ConversationHandler.END

    query = update.callback_query
    await query.answer()

    if query.data == "admin_confirm_no":
        # User cancelled — go back to refreshed list
        users = db.get_all_users_summary()
        text, kb = _build_user_list_message(users)
        await query.edit_message_text(text, reply_markup=kb, parse_mode='Markdown')
        context.user_data.pop('admin_target_id', None)
        context.user_data.pop('admin_target_name', None)
        return ADMIN_LIST

    if query.data == "admin_confirm_yes":
        target_id = context.user_data.get('admin_target_id')
        target_name = context.user_data.get('admin_target_name', 'Unknown')

        if not target_id:
            await query.edit_message_text("❌ Session expired. Please re-open /admin.")
            return ConversationHandler.END

        success = db.delete_user_and_landmarks(target_id)

        if success:
            # Cancel any live scheduled jobs for this user
            _cancel_user_jobs(context.application, target_id)

            # Refresh the list
            users = db.get_all_users_summary()
            text, kb = _build_user_list_message(users)
            await query.edit_message_text(
                f"✅ **{target_name}** has been removed.\n\n" + text,
                reply_markup=kb, parse_mode='Markdown'
            )
        else:
            await query.edit_message_text(
                "❌ **Deletion failed.** Check the server logs for details."
            )

        context.user_data.pop('admin_target_id', None)
        context.user_data.pop('admin_target_name', None)
        return ADMIN_LIST

    return ADMIN_CONFIRM_DELETE


# ------------------------------------------------------------------ #
# EXPORT HANDLER
# ------------------------------------------------------------------ #

admin_handler = ConversationHandler(
    entry_points=[CommandHandler('admin', admin_panel)],
    states={
        ADMIN_LIST: [CallbackQueryHandler(handle_admin_list, pattern=r"^admin_")],
        ADMIN_CONFIRM_DELETE: [CallbackQueryHandler(handle_confirm_delete, pattern=r"^admin_confirm_")],
    },
    fallbacks=[CommandHandler('admin', admin_panel)],  # /admin re-opens the panel from anywhere
    per_chat=True,
    per_user=True,
    allow_reentry=True
)
