'use client';

import { useCallback, useState } from 'react';
import { CatalogoAlunoView } from './CatalogoAlunoView';
import { IdentificacaoAluno } from './IdentificacaoAluno';
import {
  useIdentidadeAluno,
  type IdentidadeAluno,
} from '@/features/aluno/useIdentidadeAluno';

/**
 * Orquestra a área do aluno: sem identidade mostra a seleção de nome; com
 * identidade, o catálogo. Uma resposta 403/404 do catálogo limpa a identificação
 * e retorna à seleção com aviso.
 */
export function AreaAluno() {
  const { aluno, identificar, limpar } = useIdentidadeAluno();
  const [aviso, setAviso] = useState<string | null>(null);

  const identificarAluno = useCallback(
    (escolhido: IdentidadeAluno) => {
      setAviso(null);
      identificar(escolhido);
    },
    [identificar],
  );

  const sessaoInvalida = useCallback(
    (mensagem: string) => {
      setAviso(mensagem);
      limpar();
    },
    [limpar],
  );

  if (!aluno) {
    return <IdentificacaoAluno onIdentificar={identificarAluno} aviso={aviso} />;
  }

  return <CatalogoAlunoView aluno={aluno} onSessaoInvalida={sessaoInvalida} />;
}
