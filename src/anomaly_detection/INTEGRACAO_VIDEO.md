# Integração de vídeo

O módulo do Cae deve ser independente do monitor e expor uma função Python:

```python
def analyze_video(video_path: str) -> dict:
    # Processar vídeo real; exemplo apenas do formato de retorno:
    return {
        "status": "CONCLUIDA",
        "findings": [{
            "type": "DESVIO_POSTURAL",
            "description": "Desvio conforme regra documentada pelo analisador.",
            "severity": "MEDIO",
            "offset_seconds": 12.5,
            "frame_number": 375,
            "confidence": 0.87,
        }],
        "summary": "Um achado para revisão.",
    }
```

Esse exemplo ilustra o contrato; não é um detector. Instale o módulo no ambiente e
configure `--video PATH --video-analyzer modulo_cae:analyze_video`.
`VideoFunctionAdapter` carrega a função, valida o dicionário e retorna
`VideoAnalysisResult`. O único protocolo interno é `VideoAnalyzerProtocol`, com
`analyze_video(video_path) -> VideoAnalysisResult`. Não há exigência de importar o
monitor, usar modelos específicos ou implementar métodos adicionais.

`status` e `findings` são obrigatórios. Estados válidos:

- `CONCLUIDA`: zero ou mais achados; cada achado gera um alerta real.
- `INCONCLUSIVA`: `findings: []` e `summary` com motivo não vazio; sem alerta clínico.
- `SIMULADA`: demonstração apenas; alertas com `simulated: true`, excluídos do risco.

Cada achado exige `type` e `description` não vazios e `severity` em `CRITICO` (P1),
`ALTO` (P2), `MEDIO` (P3), `BAIXO` (P4). Campos opcionais: `offset_seconds` não
negativo, `frame_number` inteiro não negativo, `confidence` entre 0 e 1. Outras
evidências JSON, como ângulos e regra aplicada, são preservadas. Não invente
confiança, data ou evidências que não foram medidas.

No resultado, `duration_seconds` não negativo e `frames_analyzed` inteiro não
negativo são opcionais. Arquivo ausente, formato inválido ou falha de processamento
devem gerar exceção com mensagem. Contrato inválido ou exceção são registrados como
`FALHA`. Sem analisador, o monitor registra `NAO_INTEGRADO`. Esses estados não são
análises concluídas sem achados.

`--video-stub` usa `VideoAnalyzerStub`, que gera um único achado de demonstração e
não abre arquivo. O relatório sempre será parcial com esse stub.

Para o aceite final, fornecer o módulo, dependências, regra/severidade documentadas
e vídeo real com o instante esperado do achado. Veja o [desenho completo](../../docs/Arquitetura-e-System-Design.md)
e os [comandos e critérios de aceite](../../README.md).
