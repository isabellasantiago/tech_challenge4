# Plano de execução da arquitetura multimodal

## Objetivo

Entregar em duas etapas uma pipeline executável que processe áudio, sinais vitais e prescrições, gere alertas e um relatório consolidado e integre vídeo. A etapa 1 valida o fluxo offline com um stub identificado como simulado; a etapa 2 integra o módulo e o vídeo reais do Cae e valida a chamada real à OpenAI.

## Implementação

Os quatro passos abaixo pertencem à **etapa 1**. Ao concluí-los, todo o código de integração estará implementado e validado com uma implementação substituta, deixando o sistema pronto para receber o módulo do Cae. Desde que o módulo cumpra o contrato acordado, sua chegada não exigirá desenvolver novos componentes de integração.

1. **Criar a execução integrada**
   - Substituir o ponto de entrada atual por um comando `tech-challenge4` que receba `--patient-id` e `--audio-dir`. O vídeo é opcional: aceitar `--video PATH` com `--video-analyzer modulo:funcao`, `--video-stub`, ou nenhuma opção de vídeo; neste último caso, registrar `NAO_INTEGRADO`.
   - Usar o CSV sintético existente e duas prescrições sintéticas fixas, em ordem cronológica. Criar um novo `PatientMonitor` para o único paciente de cada execução.
   - Salvar o relatório em `output/report.json` e acrescentar alertas a `output/alerts.jsonl`. Documentar os caminhos e permitir sobrescrevê-los por opções do comando.
   - Ajustar empacotamento e imports para que o comando encontre os módulos de áudio e anomalias após a instalação.

2. **Preparar a integração de vídeo**
   - Consolidar o contrato interno em um único protocolo com `analyze_video(video_path)`. Criar um adaptador que carregue a função `modulo:funcao`, valide o dicionário acordado e o converta para o resultado interno.
   - Implementar um stub com um achado de exemplo e `status: SIMULADA`. Seus alertas devem conter `simulated: true` e ficar fora do cálculo do risco real.
   - Implementar `PatientMonitor.process_video_analysis`: registrar resultado e evidências, converter severidades conhecidas em alertas e distinguir análise concluída, inconclusiva, simulada, falha e módulo não integrado.

3. **Integrar as demais modalidades**
   - Chamar a pipeline real de áudio e passar `clinical_assessment` ao monitor, preservando métricas e achados no relatório. Usar a transcrição fornecida pelo DAIC-WOZ.
   - Processar as leituras do CSV e as duas prescrições pelo mesmo monitor. Validar células numéricas, valores ausentes e faixas possíveis; processar medições válidas e registrar erros de dados.
   - Corrigir a classificação de SpO₂ de 100%. Com histórico constante, marcar o Z-score como indisponível e registrar a mudança sem gerar alerta estatístico; os limiares existentes continuam sendo aplicados.

4. **Consolidar alertas e relatório**
   - Gerar UUID por alerta; exibir alertas no console e gravá-los em JSONL com paciente, origem, prioridade, evidências e indicação de simulação.
   - Ampliar o relatório do monitor com resultados e estados de todas as modalidades, limitações e estado da execução. `alerts` será uma lista de alertas completos. Adicionar `INDETERMINADO` ao enum de risco. Calcular o risco real apenas por alertas reais; se não houver alertas reais e a avaliação estiver incompleta, usar `INDETERMINADO`.
   - Continuar processando as demais modalidades quando uma falhar. Marcar a execução como parcial em caso de ausência, falha, dados inválidos, resultado inconclusivo, uso do stub ou falha de gravação. Retornar código zero quando o comando concluir o processamento e gravar as saídas, mesmo que o relatório seja parcial; retornar código diferente de zero em falha operacional, como não conseguir gravar o relatório ou o JSONL, e informar o erro no console.
   - Atualizar README e arquitetura com comandos reais, configuração da chave OpenAI, entradas, saídas, limitações e os critérios de aceite das duas etapas.

## Instalação, configuração e validação — etapa 2

Após receber o módulo do Cae e o vídeo de exemplo com resultado esperado, instalar o módulo e suas dependências e configurar sua função no comando por `--video-analyzer modulo:funcao`. O adaptador já implementado na etapa 1 valida o dicionário e o converte para o tipo interno. Restará validar a execução com vídeo real e chamada real à OpenAI, conforme o aceite final abaixo.

## Verificação

- **Etapa 1:** exercitar o comando offline com stub e resposta OpenAI simulada: relatório parcial esperado, risco e alertas corretos, alerta de vídeo identificado como simulado e JSONL válido. A etapa é aceita quando a pipeline e suas saídas funcionarem de forma reproduzível.
- Verificar que, sem chave ou com erro da API, a execução continua e registra a falha da modalidade. Para a etapa 1, a resposta simulada deve permitir execução offline reproduzível.
- Verificar vídeos concluído sem achados, com achado, inconclusivo, com exceção e com resultado inválido usando implementações substitutas do contrato.
- Verificar SpO₂ de 100%, valores ausentes ou inválidos, histórico constante e leituras válidas posteriores.
- Verificar evolução das duas prescrições, UUIDs distintos entre execuções, falhas de gravação e códigos de saída.
- Confirmar que uma função substituta no formato esperado para Cae pode ser carregada pelo comando sem alterar o monitor.
- **Etapa 2:** aceitar a integração final somente após processar áudio/transcrição com chamada real à OpenAI e vídeo real do Cae, junto às entradas sintéticas de sinais vitais e prescrições, registrando resultados e evidências no relatório.

## Premissas

- A demonstração usa um paciente fictício por execução; as entradas de modalidades diferentes são associadas a esse identificador para fins demonstrativos.
- O módulo e o vídeo reais do Cae ainda não estão disponíveis. A etapa 1 pode ser aceita sem eles, com relatório de execução parcial; a execução `COMPLETA` e o aceite da etapa 2 dependem da integração e validação dos artefatos reais.
- Não haverá transcrição automática, serviço Azure nem entrega de alertas a um serviço externo nesta fase.
