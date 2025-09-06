# llm/gradio_demo.py
import os
import gradio as gr
from client import GeminiClient
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)

# Initialize Gemini client
api_key = os.getenv("GEMINI_API_KEY")
model = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

if not api_key:
    raise ValueError("GEMINI_API_KEY environment variable is required")

llm_client = GeminiClient(
    api_key=api_key,
    model=model,
    rate_limit=60,  # Higher limit for demo
    cache_enabled=True
)

def classify_email_demo(sender, subject, body):
    """Demo function for email classification"""
    try:
        # Validate inputs
        if not sender or not subject or not body:
            return "Lỗi: Vui lòng điền đầy đủ thông tin email", "", 0.0, ""
        
        # Call LLM
        result = llm_client.classify_email(sender, subject, body)
        
        if result:
            # Format output
            label_vietnamese = "Lừa đảo" if result.label == "phishing" else "Hợp lệ"
            confidence_percent = result.confidence * 100
            
            return (
                f"Kết quả: {label_vietnamese}",
                result.explanation,
                confidence_percent,
                f"Model: {result.model}, Tokens: {result.tokens_used or 'N/A'}"
            )
        else:
            return "Lỗi: Không thể phân loại email", "", 0.0, "Lỗi kết nối hoặc API"
            
    except Exception as e:
        return f"Lỗi: {str(e)}", "", 0.0, ""

# Sample data for demo
sample_phishing = {
    "sender": "security@fake-bank.com",
    "subject": "URGENT: Your account will be suspended",
    "body": "Your account has been compromised. Click here to verify: http://phishing-example.com/verify. Act now to avoid permanent account closure."
}

sample_legit = {
    "sender": "noreply@company.com",
    "subject": "Weekly team meeting reminder",
    "body": "Hi Team, Just a reminder that our weekly team meeting is scheduled for tomorrow at 2 PM in the conference room. Please let me know if you have any agenda items. Thanks, Sarah"
}

def load_phishing_sample():
    return sample_phishing["sender"], sample_phishing["subject"], sample_phishing["body"]

def load_legit_sample():
    return sample_legit["sender"], sample_legit["subject"], sample_legit["body"]

# Create Gradio interface
with gr.Blocks(title="Phishing Email Detection Demo", theme=gr.themes.Soft()) as demo:
    gr.Markdown("""
    # 🚨 Demo Phát hiện Email Lừa đảo
    
    Sử dụng AI để phân tích và phát hiện email lừa đảo (phishing) bằng tiếng Việt.
    
    **Hướng dẫn sử dụng:**
    1. Nhập thông tin email vào các trường bên dưới
    2. Hoặc click "Mẫu email lừa đảo" / "Mẫu email hợp lệ" để tải ví dụ
    3. Click "Phân tích Email" để xem kết quả
    """)
    
    with gr.Row():
        with gr.Column(scale=2):
            gr.Markdown("### 📧 Thông tin Email")
            
            sender_input = gr.Textbox(
                label="Người gửi",
                placeholder="example@domain.com",
                lines=1
            )
            
            subject_input = gr.Textbox(
                label="Tiêu đề",
                placeholder="Nhập tiêu đề email...",
                lines=1
            )
            
            body_input = gr.Textbox(
                label="Nội dung",
                placeholder="Nhập nội dung email...",
                lines=8
            )
            
            with gr.Row():
                analyze_btn = gr.Button("🔍 Phân tích Email", variant="primary")
                clear_btn = gr.Button("🗑️ Xóa", variant="secondary")
            
            with gr.Row():
                sample_phishing_btn = gr.Button("📋 Mẫu email lừa đảo", variant="secondary")
                sample_legit_btn = gr.Button("📋 Mẫu email hợp lệ", variant="secondary")
        
        with gr.Column(scale=2):
            gr.Markdown("### 🤖 Kết quả Phân tích")
            
            result_output = gr.Textbox(
                label="Phân loại",
                lines=1,
                interactive=False
            )
            
            explanation_output = gr.Textbox(
                label="Giải thích",
                lines=4,
                interactive=False
            )
            
            confidence_output = gr.Slider(
                label="Độ tin cậy (%)",
                minimum=0,
                maximum=100,
                value=0,
                interactive=False
            )
            
            metadata_output = gr.Textbox(
                label="Thông tin kỹ thuật",
                lines=1,
                interactive=False
            )
    
    # Event handlers
    analyze_btn.click(
        classify_email_demo,
        inputs=[sender_input, subject_input, body_input],
        outputs=[result_output, explanation_output, confidence_output, metadata_output]
    )
    
    clear_btn.click(
        lambda: ("", "", "", "", "", 0, ""),
        outputs=[sender_input, subject_input, body_input, result_output, explanation_output, confidence_output, metadata_output]
    )
    
    sample_phishing_btn.click(
        load_phishing_sample,
        outputs=[sender_input, subject_input, body_input]
    )
    
    sample_legit_btn.click(
        load_legit_sample,
        outputs=[sender_input, subject_input, body_input]
    )
    
    gr.Markdown("""
    ---
    ### ℹ️ Thông tin thêm
    
    - **Model AI**: GPT-4o Mini/4o
    - **Ngôn ngữ**: Tiếng Việt
    - **Chức năng**: Phát hiện email lừa đảo tự động
    - **Bảo mật**: Dữ liệu được mã hóa và không lưu trữ
    
    ⚠️ **Lưu ý**: Đây chỉ là demo. Không nhập thông tin nhạy cảm thực tế.
    """)

if __name__ == "__main__":
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True
    )
