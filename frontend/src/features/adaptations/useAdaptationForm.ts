'use client';

import { zodResolver } from '@hookform/resolvers/zod';
import { useCallback, useState } from 'react';
import { useForm } from 'react-hook-form';
import { z } from 'zod';
import { ErroApi, mensagemDoErro } from '@/services/api/erros';
import { LIMITES } from '@/types/schemas';
import { M } from '@/lib/mensagens';
import type {
  AdaptacaoInput,
  AdaptacaoUploadInput,
  FormatoSaida,
  JobResposta,
  NivelDetalhe,
  PerfilDestinatario,
} from '@/types/novamente';
import { useCreateAdaptation, type Envio } from './useCreateAdaptation';

// Mesma contagem do contador da UI: pontos de código, não bytes nem unidades UTF-16.
const contarCaracteres = (texto: string) => Array.from(texto).length;

const FormularioSchema = z
  .object({
    modo: z.enum(['texto', 'arquivo']),
    documento_titulo: z.string(),
    documento_conteudo: z.string().optional(),
    arquivo: z.custom<File>().nullable().optional(),
    perfil_destinatario: z.enum(['Iniciante', 'Desenvolvedor', 'LiderTecnico', 'Gestor']),
    formato_saida: z.enum(['Flashcards', 'Quiz', 'Tutorial', 'ResumoExecutivo']),
    nicho_setor: z.enum(['Fintech', 'Saude', 'Ecommerce', 'Geral']),
    nivel_detalhe: z.enum(['Didatico', 'Tecnico', 'Executivo']),
  })
  .superRefine((valores, ctx) => {
    const titulo = valores.documento_titulo.trim();
    if (contarCaracteres(titulo) < LIMITES.tituloMin || contarCaracteres(titulo) > LIMITES.tituloMax) {
      ctx.addIssue({ code: 'custom', path: ['documento_titulo'], message: M.formulario.erros.titulo });
    }
    if (valores.modo === 'texto') {
      const texto = (valores.documento_conteudo ?? '').trim();
      const total = contarCaracteres(texto);
      if (total < LIMITES.textoMin) {
        ctx.addIssue({ code: 'custom', path: ['documento_conteudo'], message: M.formulario.erros.textoMin });
      } else if (total > LIMITES.textoMax) {
        ctx.addIssue({ code: 'custom', path: ['documento_conteudo'], message: M.formulario.erros.textoMax });
      }
    } else {
      if (!valores.arquivo) {
        ctx.addIssue({ code: 'custom', path: ['arquivo'], message: M.formulario.erros.arquivoObrigatorio });
      } else {
        if (valores.arquivo.size === 0) {
          ctx.addIssue({ code: 'custom', path: ['arquivo'], message: M.formulario.erros.arquivoVazio });
        }
        if (valores.arquivo.size > LIMITES.arquivoMaxBytes) {
          ctx.addIssue({ code: 'custom', path: ['arquivo'], message: M.formulario.erros.arquivoGrande });
        }
        if (!/\.(pdf|md|txt)$/i.test(valores.arquivo.name)) {
          ctx.addIssue({ code: 'custom', path: ['arquivo'], message: M.formulario.erros.arquivoTipo });
        }
      }
    }
  });

export type ValoresFormulario = z.infer<typeof FormularioSchema>;
export type Aba = 'texto' | 'arquivo';

export interface Cenario {
  titulo: string;
  perfil: PerfilDestinatario;
  formato: FormatoSaida;
  nivel: NivelDetalhe;
}

const VALORES_INICIAIS: ValoresFormulario = {
  modo: 'texto',
  documento_titulo: '',
  documento_conteudo: '',
  arquivo: null,
  perfil_destinatario: 'Iniciante',
  formato_saida: 'Flashcards',
  nicho_setor: 'Geral',
  nivel_detalhe: 'Didatico',
};

const CAMPOS_CONHECIDOS = new Set<string>(Object.keys(VALORES_INICIAIS));

function paraEnvio(valores: ValoresFormulario): Envio {
  const base = {
    documento_titulo: valores.documento_titulo.trim(),
    perfil_destinatario: valores.perfil_destinatario,
    formato_saida: valores.formato_saida,
    nicho_setor: valores.nicho_setor,
    nivel_detalhe: valores.nivel_detalhe,
  };
  return valores.modo === 'texto'
    ? ({ ...base, documento_conteudo: (valores.documento_conteudo ?? '').trim() } satisfies AdaptacaoInput)
    : ({ ...base, arquivo: valores.arquivo as File } satisfies AdaptacaoUploadInput);
}

export function useAdaptationForm(
  onCriado: (job: JobResposta, repetir: () => Promise<JobResposta | null>) => void,
) {
  const { criar, repetir, enviando } = useCreateAdaptation();
  const [aba, setAba] = useState<Aba>('texto');
  const [erroGeral, setErroGeral] = useState<string | null>(null);

  const form = useForm<ValoresFormulario>({
    resolver: zodResolver(FormularioSchema),
    mode: 'onBlur',
    defaultValues: VALORES_INICIAIS,
  });

  const mapearErro = useCallback(
    (erro: unknown) => {
      if (erro instanceof ErroApi && erro.problema.erro.campos) {
        for (const [campo, mensagem] of Object.entries(erro.problema.erro.campos)) {
          if (!CAMPOS_CONHECIDOS.has(campo)) continue;
          form.setError(campo as keyof ValoresFormulario, { type: 'server', message: mensagem });
        }
      }
      setErroGeral(mensagemDoErro(erro));
    },
    [form],
  );

  const enviarValores = useCallback(
    async (valores: ValoresFormulario) => {
      setErroGeral(null);
      try {
        const job = await criar(paraEnvio(valores));
        onCriado(job, repetir);
      } catch (erro) {
        mapearErro(erro);
      }
    },
    [criar, mapearErro, onCriado, repetir],
  );

  const enviar = form.handleSubmit(enviarValores);

  const trocarAba = useCallback(
    (nova: Aba) => {
      setAba(nova);
      setErroGeral(null);
      form.clearErrors();
      form.setValue('modo', nova);
      if (nova === 'texto') form.setValue('arquivo', null);
      else form.setValue('documento_conteudo', '');
    },
    [form],
  );

  const dispararCenario = useCallback(
    async (cenario: Cenario, documento: string) => {
      const conteudo =
        documento.length > 0
          ? documento.repeat(Math.ceil(LIMITES.textoMin / contarCaracteres(documento)) + 1)
          : documento;
      const valores: ValoresFormulario = {
        ...VALORES_INICIAIS,
        modo: 'texto',
        documento_titulo: cenario.titulo,
        documento_conteudo: conteudo,
        perfil_destinatario: cenario.perfil,
        formato_saida: cenario.formato,
        nivel_detalhe: cenario.nivel,
      };
      form.reset(valores);
      setAba('texto');
      await enviarValores(valores);
    },
    [enviarValores, form],
  );

  return { form, aba, trocarAba, enviar, enviando, erroGeral, dispararCenario };
}
