import os
import sys
import io
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
from sqlalchemy import func

# Thêm thư mục backend vào sys.path để import các module từ app
backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
sys.path.append(backend_dir)

from app.core.database import SessionLocal
from app.modules.evaluation.models import ArticleEvaluation
from app.modules.news.models import ArticleIdentity

def calculate_confusion_matrix():
    db = SessionLocal()
    try:
        # Lấy tất cả các bản ghi đánh giá đã được xác minh (is_verified = True)
        evals = db.query(ArticleEvaluation).filter(ArticleEvaluation.is_verified == True).all()
        
        if not evals:
            print("="*60)
            print(" KẾT QUẢ TÍNH TOÁN CONFUSION MATRIX ")
            print("="*60)
            print("Chưa có dữ liệu bài viết được xác minh nhãn thủ công (human_label).")
            print("Vui lòng thực hiện gán nhãn trên giao diện quản trị hoặc import file Excel.")
            return
            
        print("="*70)
        print(" KẾT QUẢ TÍNH TOÁN CONFUSION MATRIX (MA TRẬN NHẦM LẪN) ")
        print("="*70)
        print(f"Tổng số bài viết đã được xác minh nhãn thủ công: {len(evals)}")
        print("-"*70)
        
        labels = ["relevant", "noise", "irrelevant", "unsure"]
        
        # Ma trận nhầm lẫn: Dòng = Human Label (Nhãn thực tế), Cột = LLM Label (Nhãn dự đoán)
        # confusion[human_label][llm_label]
        confusion = {h_lbl: {l_lbl: 0 for l_lbl in labels} for h_lbl in labels}
        
        for e in evals:
            h_lbl = e.human_label
            l_lbl = e.llm_label
            
            # Gán nhãn mặc định nếu bị trống
            if not h_lbl:
                h_lbl = "unsure"
            if not l_lbl:
                # Fallback dựa vào việc có event_id hay không
                article = db.query(ArticleIdentity).filter(ArticleIdentity.id == e.article_id).first()
                l_lbl = "relevant" if (article and article.event_id) else "irrelevant"
                
            if h_lbl in labels and l_lbl in labels:
                confusion[h_lbl][l_lbl] += 1
                
        # Hiển thị ma trận nhầm lẫn dạng bảng
        print("BẢNG MA TRẬN NHẦM LẪN (CONFUSION MATRIX):")
        print("Dòng: Nhãn thực tế (Human) | Cột: Nhãn dự đoán (LLM)")
        print()
        print(f"{'Human \\ LLM':<15} | {'relevant':^10} | {'noise':^10} | {'irrelevant':^10} | {'unsure':^10} | {'Tổng cộng':^10}")
        print("-" * 75)
        
        total_predictions = {l_lbl: 0 for l_lbl in labels}
        total_actuals = {h_lbl: 0 for h_lbl in labels}
        
        for h_lbl in labels:
            row_total = sum(confusion[h_lbl][l_lbl] for l_lbl in labels)
            total_actuals[h_lbl] = row_total
            print(f"{h_lbl:<15} | ", end="")
            for l_lbl in labels:
                val = confusion[h_lbl][l_lbl]
                total_predictions[l_lbl] += val
                print(f"{val:^10} | ", end="")
            print(f"{row_total:^10}")
            
        print("-" * 75)
        grand_total = len(evals)
        print(f"{'Tổng cộng':<15} | ", end="")
        for l_lbl in labels:
            print(f"{total_predictions[l_lbl]:^10} | ", end="")
        print(f"{grand_total:^10}")
        print()
        
        # Tính toán các chỉ số đánh giá chi tiết
        print("CHỈ SỐ ĐÁNH GIÁ CHI TIẾT THEO TỪNG NHÃN (CLASS-WISE METRICS):")
        print(f"{'Nhãn (Class)':<15} | {'Precision':^12} | {'Recall':^12} | {'F1-Score':^12} | {'Hỗ trợ':^10}")
        print("-" * 70)
        
        total_correct = 0
        for lbl in labels:
            tp = confusion[lbl][lbl]
            total_correct += tp
            
            # Precision = TP / (TP + FP) -> TP / Total Predictions for this class
            pred_total = total_predictions[lbl]
            precision = (tp / pred_total * 100) if pred_total > 0 else 0
            
            # Recall = TP / (TP + FN) -> TP / Total Actuals for this class
            actual_total = total_actuals[lbl]
            recall = (tp / actual_total * 100) if actual_total > 0 else 0
            
            # F1 = 2 * P * R / (P + R)
            f1 = (2 * precision * recall / (precision + recall)) if (precision + recall) > 0 else 0
            
            print(f"{lbl:<15} | {precision:>10.2f}% | {recall:>10.2f}% | {f1:>10.2f}% | {actual_total:^10}")
            
        print("-" * 70)
        
        # Chỉ số chung
        accuracy = (total_correct / grand_total * 100) if grand_total > 0 else 0
        print(f"{'Độ chính xác toàn cục (Overall Accuracy):':<40} {accuracy:.2f}%")
        
        # Tính tỷ lệ lỗi False Positive của hệ thống y tế (LLM bảo relevant nhưng thực tế là noise hoặc irrelevant)
        # FP cho 'relevant':
        tp_rel = confusion["relevant"]["relevant"]
        fp_rel = sum(confusion[h_lbl]["relevant"] for h_lbl in labels if h_lbl != "relevant")
        fn_rel = sum(confusion["relevant"][l_lbl] for l_lbl in labels if l_lbl != "relevant")
        
        print("-" * 70)
        print("PHÂN TÍCH CHUYÊN SÂU TÍN HIỆU DỊCH TỄ (RELEVANT):")
        print(f"- Số ca Đúng Tích Cực (True Positives - TP): {tp_rel}")
        print(f"- Số ca Dương Tính Giả (False Positives - FP): {fp_rel} (Hệ thống dự báo Relevant nhưng Người dùng gắn nhãn khác)")
        print(f"- Số ca Âm Tính Giả (False Negatives - FN): {fn_rel} (Người dùng gắn nhãn Relevant nhưng Hệ thống bỏ sót)")
        
        precision_rel = (tp_rel / (tp_rel + fp_rel) * 100) if (tp_rel + fp_rel) > 0 else 0
        recall_rel = (tp_rel / (tp_rel + fn_rel) * 100) if (tp_rel + fn_rel) > 0 else 0
        f1_rel = (2 * precision_rel * recall_rel / (precision_rel + recall_rel)) if (precision_rel + recall_rel) > 0 else 0
        
        print(f"- Độ chính xác tín hiệu dịch tễ (Precision): {precision_rel:.2f}%")
        print(f"- Tỷ lệ bao phủ tín hiệu (Recall): {recall_rel:.2f}%")
        print(f"- Chỉ số F1-Score của dịch tễ: {f1_rel:.2f}%")
        print("=" * 70)
        
    finally:
        db.close()

if __name__ == "__main__":
    calculate_confusion_matrix()
