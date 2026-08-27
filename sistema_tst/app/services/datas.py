from datetime import date, timedelta


def ajustar_domingo(data: date) -> date:
    """Move domingos para a segunda-feira seguinte."""
    return data + timedelta(days=1) if data.weekday() == 6 else data


def calcular_datas_sequenciais(data_inicial: date, quantidade: int) -> list[date]:
    """Gera datas consecutivas, ignorando domingos."""
    datas: list[date] = []
    atual = ajustar_domingo(data_inicial)
    while len(datas) < quantidade:
        if atual.weekday() != 6:
            datas.append(atual)
        atual += timedelta(days=1)
    return datas
