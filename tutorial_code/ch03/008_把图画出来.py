# 方式 1:Jupyter Notebook 中显示
from IPython.display import Image, display
display(Image(graph.get_graph().draw_mermaid_png()))

# 方式 2:打印 Mermaid 源码(贴到 mermaid.live 看)
print(graph.get_graph().draw_mermaid())

# 方式 3:纯文本(终端就能看)
print(graph.get_graph().draw_ascii())