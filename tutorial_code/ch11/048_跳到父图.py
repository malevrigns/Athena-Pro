return Command(
    goto="parent_supervisor",
    graph=Command.PARENT,    # 跳出当前子图
    update={...},
)