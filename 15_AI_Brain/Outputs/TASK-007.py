**Bug**

In the `reg_photo_receive` handler the uploaded photo was read but never stored in the user data flow nor did the function transition to the next conversation state.  
Because of this, after the photo message the conversation got stuck – the bot never asked for the remaining patient details and the photo was lost.  

**Fix**

Store the image bytes in `context.user_data["new_patient"]["Photo"]` and forward the flow to `_reg_ask_fields_or_continue`, which will prompt for missing information or check for duplicates.

```python
# --------------- রেজিস্ট্রেশন: ফটো পেতে ------------

async def reg_photo_receive(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Get the latest photo the user sent
    photo = update.message.photo[-1]
    tg_file = await photo.get_file()

    # Download image bytes
    image_bytes = bytes(await tg_file.download_as_bytearray())

    # ------------------------------------------------------------------
    # *** Bug fix starts here ***
    # ------------------------------------------------------------------
    # Store the raw image bytes so they can be used later in the
    # registration workflow (e.g., OCR or manual upload to a
    # storage backend).  The previous implementation forgot this step,
    # resulting in lost data and the conversation never moving on.
    new_patient = context.user_data.setdefault("new_patient", {})
    new_patient["Photo"] = image_bytes

    # Continue the registration conversation.  The helper function
    # _reg_ask_fields_or_continue() automatically decides whether
    # we still need to ask for missing fields or proceed to duplicate
    # checks.  Returning its value triggers the proper next state.
    # ------------------------------------------------------------------
    return await _reg_ask_fields_or_continue(update, context)
    # ------------------------------------------------------------
```

*Location*: Replace the body of `reg_photo_receive` in `03_Bot/bot.py` (after the line computing `image_bytes`).  

*Why this resolves the bug*:  
- Photo bytes are no longer discarded – they are preserved for the later steps of registration.  
- The conversation correctly advances to the next state instead of ending prematurely.