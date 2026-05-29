"""
工具栏SVG图标定义
所有图标均为24x24的矢量图形
"""
# ... existing code ...

TOOLBAR_ICONS = {
    "rectangle": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#000000" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <rect x="3" y="3" width="18" height="18" rx="2" ry="2"/>
  <circle cx="8.5" cy="8.5" r="1.5"/>
</svg>""",

    "arrow": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#000000" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <line x1="5" y1="19" x2="19" y2="5"/>
  <polyline points="10 5 19 5 19 14"/>
</svg>""",

    "pen": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#000000" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M12 19l7-7 3 3-7 7-3-3z"/>
  <path d="M18 13l-1.5-7.5L2 2l3.5 14.5L13 18l5-5z"/>
  <path d="M2 2l7.586 7.586"/>
  <circle cx="11" cy="11" r="2"/>
</svg>""",

    "highlighter": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#000000" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M12 20h9"/>
  <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"/>
</svg>""",

    "mosaic": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#000000" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <rect x="2" y="2" width="6" height="6" fill="#000000"/>
  <rect x="9" y="2" width="6" height="6"/>
  <rect x="16" y="2" width="6" height="6" fill="#000000"/>
  <rect x="2" y="9" width="6" height="6"/>
  <rect x="9" y="9" width="6" height="6" fill="#000000"/>
  <rect x="16" y="9" width="6" height="6"/>
  <rect x="2" y="16" width="6" height="6" fill="#000000"/>
  <rect x="9" y="16" width="6" height="6"/>
  <rect x="16" y="16" width="6" height="6" fill="#000000"/>
</svg>""",


    "text": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#000000" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <polyline points="4 7 4 4 20 4 20 7"/>
  <line x1="9" y1="20" x2="15" y2="20"/>
  <line x1="12" y1="4" x2="12" y2="20"/>
</svg>""",

    "eraser": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#000000" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M20 20H7L3 16c-.8-.8-.8-2 0-2.8L14.8 1.4c.8-.8 2-.8 2.8 0l5 5c.8.8.8 2 0 2.8L11 20"/>
  <path d="M6 11l8 8"/>
</svg>""",

    "eraser_dot": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#000000" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="12" cy="12" r="5" fill="#000000"/>
  <circle cx="12" cy="12" r="9" stroke-dasharray="3,2"/>
</svg>""",

    "eraser_fill": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#000000" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round">
  <rect x="3" y="3" width="18" height="18" rx="2"/>
  <circle cx="6.5" cy="6.5" r="1.5" fill="#000000" stroke="none"/>
  <circle cx="11" cy="6.5" r="1.5" fill="#000000" stroke="none"/>
  <circle cx="15.5" cy="6.5" r="1.5" fill="#000000" stroke="none"/>
  <circle cx="6.5" cy="11" r="1.5" fill="#000000" stroke="none"/>
  <circle cx="11" cy="11" r="1.5" fill="#000000" stroke="none"/>
  <circle cx="15.5" cy="11" r="1.5" fill="#000000" stroke="none"/>
  <circle cx="6.5" cy="15.5" r="1.5" fill="#000000" stroke="none"/>
  <circle cx="11" cy="15.5" r="1.5" fill="#000000" stroke="none"/>
  <circle cx="15.5" cy="15.5" r="1.5" fill="#000000" stroke="none"/>
</svg>""",

    "undo": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
  <path d="M3 7v6h6"/>
  <path d="M21 17a9 9 0 0 0-9-9 9 9 0 0 0-6 2.3L3 13"/>
</svg>""",

    "redo": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
  <path d="M21 7v6h-6"/>
  <path d="M3 17a9 9 0 0 1 9-9 9 9 0 0 1 6 2.3l3 2.7"/>
</svg>""",

    "close": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="12" cy="12" r="10"/>
  <line x1="15" y1="9" x2="9" y2="15"/>
  <line x1="9" y1="9" x2="15" y2="15"/>
</svg>""",

    "pin": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#000000" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <line x1="12" y1="17" x2="12" y2="22"/>
  <path d="M5 17h14v-1.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V6h1a2 2 0 0 0 0-4H8a2 2 0 0 0 0 4h1v4.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24Z"/>
</svg>""",


    "save": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#000000" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"/>
  <polyline points="17 21 17 13 7 13 7 21"/>
  <polyline points="7 3 7 8 15 8"/>
</svg>""",

    "done": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#000000" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="12" cy="12" r="10" fill="#207ff0" stroke="#207ff0"/>
  <polyline points="8 12 11 15 16 9" stroke="#ffffff" stroke-width="2.5"/>
</svg>""",

    "copy": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#000000" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
  <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
</svg>""",

    "ellipse": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#000000" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <ellipse cx="12" cy="12" rx="10" ry="7"/>
</svg>""",

    "line": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#000000" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <line x1="4" y1="20" x2="20" y2="4"/>
</svg>""",

    "blur": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#000000" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="12" cy="12" r="10" stroke-dasharray="4 3"/>
  <path d="M12 2v20" stroke-dasharray="3 2"/>
  <path d="M2 12h20" stroke-dasharray="3 2"/>
  <path d="M4.93 4.93l14.14 14.14"/>
  <path d="M19.07 4.93L4.93 19.07"/>
</svg>""",

    "number_marker": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#000000" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="12" cy="12" r="10" fill="#000000"/>
  <text x="12" y="16" font-size="11" font-weight="bold" text-anchor="middle" fill="#ffffff" stroke="none">1</text>
</svg>""",

    "magnifier": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#000000" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="11" cy="11" r="7"/>
  <line x1="16.5" y1="16.5" x2="21" y2="21"/>
  <line x1="8" y1="11" x2="14" y2="11"/>
  <line x1="11" y1="8" x2="11" y2="14"/>
</svg>""",

    "OCR": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="#000000" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">                                                                                                                                                <!-- 左上角角标 -->
            <path d="M3 7V3h4"/>
            <!-- 右上角角标 -->
            <path d="M21 7V3h-4"/>
            <!-- 左下角角标 -->
            <path d="M3 17v4h4"/>
            <!-- 右下角角标 -->
            <path d="M21 17v4h-4"/>
            <!-- 中间的 T 字母 -->
            <path d="M12 8v8M8 8h8"/>
</svg>""",
            "icon": """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0    
     24 24" fill="#fff" stroke="#000000" stroke-width="1">   
       <!-- 左上矩形 -->                                     
       <rect x="5" y="4" width="6" height="7" rx="1"/>       
       <!-- 右上矩形 -->                                     
       <rect x="13" y="4" width="6" height="7" rx="1"/>      
       <!-- 左下旗帜 -->                                     
       <path d="M5 13h6v8l-3-3L5 26z"/>                      
       <!-- 右下旗帜 -->                                     
       <path d="M19 13h-6v8l3-3L19 26z"/>                 
     </svg>"""
}

# ... existing code ...



def get_icon_svg(icon_name: str) -> str:
    """获取指定图标的SVG代码"""
    return TOOLBAR_ICONS.get(icon_name, "")


def get_all_icon_names() -> list:
    """获取所有图标名称列表"""
    return list(TOOLBAR_ICONS.keys())
