'use client';

import { useCallback, useState } from 'react';
import { useApi } from '@/services/api/ApiProvider';
import { mensagemDoErro } from '@/services/api/erros';
import { baixarBlob } from '@/services/api/download';
import { nomeArquivoExportacao, nomeArquivoPacote } from '@/lib/formatadores';
import type { AdaptacaoPacote, FormatoExportacao } from '@/types/novamente';

export function useExport(pacote: AdaptacaoPacote | null) {
  const api = useApi();
  const [baixando, setBaixando] = useState<FormatoExportacao | 'json' | null>(null);
  const [erro, setErro] = useState<string | null>(null);

  const exportar = useCallback(
    async (formato: FormatoExportacao) => {
      if (!pacote) return;
      setErro(null);
      setBaixando(formato);
      try {
        const blob = await api.exportar(pacote.adaptacao_id, formato);
        baixarBlob(blob, nomeArquivoExportacao(pacote, formato));
      } catch (e) {
        setErro(mensagemDoErro(e));
      } finally {
        setBaixando(null);
      }
    },
    [api, pacote],
  );

  const baixarJson = useCallback(async () => {
    if (!pacote) return;
    setErro(null);
    setBaixando('json');
    try {
      const blob = await api.baixarJson(pacote.adaptacao_id);
      baixarBlob(blob, nomeArquivoPacote(pacote));
    } catch (e) {
      setErro(mensagemDoErro(e));
    } finally {
      setBaixando(null);
    }
  }, [api, pacote]);

  return {
    exportar,
    baixarJson,
    baixando,
    erro,
    csvDisponivel: pacote?.conteudo_adaptado.tipo === 'flashcards',
  };
}
