def handle_youtube_transcripts_export(chat_id):
    """
    Fetches raw transcripts from tracked YouTube channels and sends them as a text file.
    This is useful for importing into NotebookLM or other LLMs manually.
    """
    send_telegram_message(chat_id, "📜 <b>Fetching YouTube Transcripts...</b>\n\nGetting raw text from Coin Bureau, Benjamin Cowen, and Crypto Banter. Please wait.")
    
    try:
        all_content = []
        for name, cid in youtube_analyzer.CHANNELS.items():
            vid, title = youtube_analyzer.get_latest_video_id(cid)
            if vid:
                # Random delay to be safe
                time.sleep(2)
                text = youtube_analyzer.get_transcript(vid)
                if text:
                    all_content.append(f"=== CHANNEL: {name} ===\nTITLE: {title}\nURL: https://www.youtube.com/watch?v={vid}\n\nTRANSCRIPT:\n{text}\n\n")
                else:
                    all_content.append(f"=== CHANNEL: {name} ===\nTITLE: {title}\n(Transcript not available)\n\n")
            else:
                 all_content.append(f"=== CHANNEL: {name} ===\n(No recent video found)\n\n")

        if not all_content:
            send_telegram_message(chat_id, "⚠️ Could not retrieve any transcripts.")
            return

        # Combine output
        full_text = "\n".join(all_content)
        
        # Save to file
        filename = f"youtube_transcripts_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        file_path = os.path.join(os.getcwd(), filename)
        
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(full_text)
            
        # Send file
        from telegram_bot import send_telegram_document
        success = send_telegram_document(chat_id, file_path, caption="📜 Here are the raw transcripts for NotebookLM.")
        
        # Cleanup
        if os.path.exists(file_path):
            os.remove(file_path)
            
        if not success:
            send_telegram_message(chat_id, "⚠️ Failed to send transcript file. Text might be too long?")
            
    except Exception as e:
        print(f"[ERROR] Transcript export failed: {e}")
        send_telegram_message(chat_id, f"⚠️ Error exporting transcripts: {str(e)}")
