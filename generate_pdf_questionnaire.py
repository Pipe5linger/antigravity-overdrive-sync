import os
import re
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, KeepTogether, PageBreak, Flowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.colors import HexColor

class InteractiveField(Flowable):
    def __init__(self, name, width=200, height=20, multiline=False, tooltip=""):
        super().__init__()
        self.name = name
        self.width = width
        self.height = height
        self.multiline = multiline
        self.tooltip = tooltip

    def wrap(self, availWidth, availHeight):
        return self.width, self.height

    def draw(self):
        self.canv.saveState()
        # Draw a light background rectangle for visual guidance in standard readers
        self.canv.setStrokeColor(HexColor("#BBBBBB"))
        self.canv.setFillColor(HexColor("#F9F9F9"))
        self.canv.rect(0, 0, self.width, self.height, fill=True, stroke=True)
        
        # Setup form text field
        form = self.canv.acroForm
        form.textfieldRelative(
            name=self.name,
            x=0,
            y=0,
            width=self.width,
            height=self.height,
            fieldFlags='multiline' if self.multiline else '',
            borderColor=HexColor("#BBBBBB"),
            fillColor=HexColor("#F9F9F9"),
            tooltip=self.tooltip
        )
        self.canv.restoreState()

def parse_markdown_questionnaire(filepath):
    """
    Parses the questionnaire and structures sections, subsections, and questions.
    """
    with open(filepath, "r", encoding="utf-8") as f:
        content = f.read()

    lines = content.split("\n")
    structure = []
    
    current_section = None
    current_subsection = None
    current_question = None
    
    # We parse line by line
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if not line:
            i += 1
            continue
            
        if line.startswith("## Section"):
            current_section = line.replace("## ", "").strip()
            structure.append({
                "type": "section",
                "text": current_section
            })
            current_subsection = None
        elif line.startswith("### "):
            current_subsection = line.replace("### ", "").strip()
            structure.append({
                "type": "subsection",
                "text": current_subsection
            })
        elif re.match(r"^\d+\.", line):
            # Parse a question block
            q_text = line.strip()
            choice_text = ""
            why_text = ""
            
            # Read next lines to find [ CHOICE/SCALE ] and [ WHY ]
            if i + 1 < len(lines) and lines[i+1].strip().startswith("["):
                i += 1
                choice_text = lines[i].strip()
                if i + 1 < len(lines) and lines[i+1].strip().startswith("["):
                    i += 1
                    why_text = lines[i].strip()
            
            structure.append({
                "type": "question",
                "text": q_text,
                "choice_desc": choice_text,
                "why_desc": why_text
            })
        i += 1
        
    return structure

def build_pdf_questionnaire():
    md_path = Path("D:/AI/Antigravity outputs/questionnaire.md")
    pdf_path = Path("D:/AI/Antigravity outputs/questionnaire.pdf")
    
    print(f"[*] Parsing Markdown Questionnaire at: {md_path}")
    structure = parse_markdown_questionnaire(md_path)
    if not structure:
        print("[-] Failed to parse questionnaire.")
        return
        
    print(f"[*] Building interactive PDF form at: {pdf_path}")
    
    doc = SimpleDocTemplate(
        str(pdf_path),
        pagesize=letter,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )
    
    styles = getSampleStyleSheet()
    
    # Custom Styles for High-End Design
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=HexColor('#0F172A'),
        spaceAfter=15
    )
    
    desc_style = ParagraphStyle(
        'DocDesc',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10.5,
        leading=14,
        textColor=HexColor('#475569'),
        spaceAfter=25
    )
    
    section_style = ParagraphStyle(
        'SecTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=16,
        leading=20,
        textColor=HexColor('#1E3A8A'),
        spaceBefore=20,
        spaceAfter=10,
        keepWithNext=True
    )
    
    subsection_style = ParagraphStyle(
        'SubSecTitle',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=12,
        leading=16,
        textColor=HexColor('#0D9488'),
        spaceBefore=12,
        spaceAfter=8,
        keepWithNext=True
    )
    
    q_style = ParagraphStyle(
        'QuestionText',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=10,
        leading=14,
        textColor=HexColor('#1E293B'),
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )
    
    opts_style = ParagraphStyle(
        'OptionText',
        parent=styles['Normal'],
        fontName='Helvetica-Oblique',
        fontSize=9,
        leading=12,
        textColor=HexColor('#64748B'),
        spaceAfter=6,
        keepWithNext=True
    )
    
    field_label_style = ParagraphStyle(
        'FieldLabel',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8,
        leading=10,
        textColor=HexColor('#94A3B8'),
        spaceAfter=2,
        keepWithNext=True
    )
    
    story = []
    
    # Document Header
    story.append(Paragraph("Vespera's Personal Deep Profiling Questionnaire", title_style))
    story.append(Paragraph(
        "This interactive PDF contains the hybrid cognitive-psychological profiling metrics. "
        "Complete the fields directly in your PDF reader. The input boxes will expand to capture your thoughts. "
        "Save the file when done and execute the python script to parse it.",
        desc_style
    ))
    story.append(Spacer(1, 10))
    
    q_counter = 0
    
    for item in structure:
        if item["type"] == "section":
            story.append(PageBreak())
            story.append(Paragraph(item["text"], section_style))
            story.append(Spacer(1, 10))
        elif item["type"] == "subsection":
            story.append(Paragraph(item["text"], subsection_style))
            story.append(Spacer(1, 8))
        elif item["type"] == "question":
            q_counter += 1
            q_elements = []
            
            # Question block grouping to prevent awkward page splits
            q_elements.append(Paragraph(item["text"], q_style))
            
            if item["choice_desc"]:
                # Clean choice description bracket tags for reading beauty
                desc = item["choice_desc"].replace("[ CHOICE: ", "").replace("[ SCALE ", "").rstrip(" ]")
                q_elements.append(Paragraph(f"Options: {desc}", opts_style))
            
            # 1. Scale/Choice Field
            q_elements.append(Paragraph("INPUT CHOICE/SCALE HERE (Single character or score):", field_label_style))
            q_elements.append(InteractiveField(
                name=f"q_{q_counter}_val",
                width=150,
                height=18,
                tooltip=f"Choice/Scale for question {q_counter}"
            ))
            q_elements.append(Spacer(1, 4))
            
            # 2. Why/Explanation Field
            q_elements.append(Paragraph("ELABORATE / CONTEXTUALIZE:", field_label_style))
            q_elements.append(InteractiveField(
                name=f"q_{q_counter}_why",
                width=450,
                height=36,
                multiline=True,
                tooltip=f"Elaboration for question {q_counter}"
            ))
            
            q_elements.append(Spacer(1, 12))
            story.append(KeepTogether(q_elements))
            
    doc.build(story)
    print(f"[+] PDF Form compiled successfully at: {pdf_path}")

if __name__ == "__main__":
    build_pdf_questionnaire()
