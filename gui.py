import sys
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QHBoxLayout, 
                             QVBoxLayout, QTextEdit, QPushButton, QLabel, QSplitter)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont

# Import our updated dual-input analysis engine from backend.py
from backend import analyze_patent_draft

class PatentToolGUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Offline Patent Drafting & Proofreading Tool")
        self.setGeometry(200, 100, 1200, 800)  
        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # MINIMALIST VERTICAL PARTITION (Left Inputs vs Right Outputs)
        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.setHandleWidth(4) 

        # ----------------- LEFT PANEL (WITH RESIZABLE INPUTS) -----------------
        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        left_layout.setContentsMargins(0, 0, 5, 0)

        input_splitter = QSplitter(Qt.Orientation.Vertical)
        input_splitter.setHandleWidth(4)

        # Container for Claims Input
        claims_container = QWidget()
        claims_vbox = QVBoxLayout(claims_container)
        claims_vbox.setContentsMargins(0, 0, 0, 5)
        claims_label = QLabel("Patent Claims:")
        claims_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.claims_input = QTextEdit()
        self.claims_input.setPlaceholderText("1. An apparatus comprising a semiconductor layer and a metal gate.\n2. The apparatus of claim 1, further comprising a semiconductor layer...")
        claims_vbox.addWidget(claims_label)
        claims_vbox.addWidget(self.claims_input)

        # Container for Description Input
        desc_container = QWidget()
        desc_vbox = QVBoxLayout(desc_container)
        desc_vbox.setContentsMargins(0, 5, 0, 0)
        desc_label = QLabel("Detailed Description / Specification:")
        desc_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.desc_input = QTextEdit()
        self.desc_input.setPlaceholderText("Paste description here to map reference numerals (e.g., substrate 102)...")
        desc_vbox.addWidget(desc_label)
        desc_vbox.addWidget(self.desc_input)

        input_splitter.addWidget(claims_container)
        input_splitter.addWidget(desc_container)
        input_splitter.setSizes([450, 300]) 

        # Action Button
        self.analyze_btn = QPushButton("Run Proofreading & Analysis")
        self.analyze_btn.setStyleSheet("""
            QPushButton {
                background-color: #2b5c8f; 
                color: white; 
                font-weight: bold; 
                padding: 10px; 
                font-size: 13px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1e436d;
            }
        """)
        self.analyze_btn.clicked.connect(self.handle_analyze)

        left_layout.addWidget(input_splitter)
        left_layout.addWidget(self.analyze_btn)

        # ----------------- RIGHT PANEL (SEPARATE OUTPUTS) -----------------
        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.setContentsMargins(5, 0, 0, 0)

        output_splitter = QSplitter(Qt.Orientation.Vertical)
        output_splitter.setHandleWidth(4) 

        # 1. Antecedent Window Widget
        antecedent_container = QWidget()
        antecedent_vbox = QVBoxLayout(antecedent_container)
        antecedent_vbox.setContentsMargins(0, 0, 0, 5)
        ant_label = QLabel("Antecedent Basis & Dependency Analysis:")
        ant_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.antecedent_output = QTextEdit()
        self.antecedent_output.setReadOnly(True)
        self.antecedent_output.setPlaceholderText("Antecedent errors will appear here...")
        antecedent_vbox.addWidget(ant_label)
        antecedent_vbox.addWidget(self.antecedent_output)

        # 2. Reference Numeral Window Widget
        numeral_container = QWidget()
        numeral_vbox = QVBoxLayout(numeral_container)
        numeral_vbox.setContentsMargins(0, 5, 0, 0)
        num_label = QLabel("Reference Numeral Tracker:")
        num_label.setFont(QFont("Arial", 11, QFont.Weight.Bold))
        self.numeral_output = QTextEdit()
        self.numeral_output.setReadOnly(True)
        self.numeral_output.setPlaceholderText("Reference numeral mapping will appear here...")
        numeral_vbox.addWidget(num_label)
        numeral_vbox.addWidget(self.numeral_output)

        output_splitter.addWidget(antecedent_container)
        output_splitter.addWidget(numeral_container)
        right_layout.addWidget(output_splitter)

        main_splitter.addWidget(left_widget)
        main_splitter.addWidget(right_widget)
        
        main_splitter.setSizes([600, 600])
        output_splitter.setSizes([400, 400])

        main_layout.addWidget(main_splitter)

    def handle_analyze(self):
        """Extracts text streams from both inputs and runs the unified engine."""
        raw_claims = self.claims_input.toPlainText()
        description_text = self.desc_input.toPlainText()

        if not raw_claims.strip():
            self.antecedent_output.setHtml("<b style='color: red;'>Please enter claims to check.</b>")
            return

        # 1. Standardize line breaks
        normalized_lines = raw_claims.replace('\r\n', '\n').replace('\r', '\n').split('\n')
        claims_text = " \n ".join([line.strip() for line in normalized_lines if line.strip()])

        # 2. IRONCLAD SPACE RECOVERY SYSTEM
        # Automatically insert missing spaces around structural patent transition words
        patent_glue_words = ['plurality', 'nodes', 'node', 'gateway', 'signal', 'transmission', 'ones', 'aligned', 'signals', 'correlated', 'composite']
        
        # Inject space before joining verbs/prepositions if smashed
        for word in patent_glue_words:
            claims_text = re.sub(rf'\b({word})(of|are|is|that|to|from|using|comprising|comprises|having|has)\b', r'\1 \2', claims_text, flags=re.IGNORECASE)
            claims_text = re.sub(rf'\b(a|an|the|said)({word})\b', r'\1 \2', claims_text, flags=re.IGNORECASE)

        # Run our dual-output processing engine
        from backend import analyze_patent_draft
        antecedent_html, numerals_html = analyze_patent_draft(claims_text, description_text)
        
        # Route outputs to their respective independent GUI windows
        self.antecedent_output.setHtml(antecedent_html)
        self.numeral_output.setHtml(numerals_html)

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = PatentToolGUI()
    window.show()
    sys.exit(app.exec())