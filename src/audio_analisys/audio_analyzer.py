import os
import librosa
import glob
import numpy as np
import pandas as pd

# Limiares padronizados pela literatura (Cummins et al., 2015; Mundt et al., 2007)
PITCH_STD_THRESHOLD = 20.0  # Hz (Monotonia vocal / Embotamento afetivo)
PAUSE_RATIO_THRESHOLD = 0.35  # 35% (Lentificação psicomotora)
ENERGY_RMS_THRESHOLD = 0.01  # RMS (Astenia / Baixa energia)


class AudioAnalyzer:

    def _read_transcript_dataframe(self, transcript_path: str) -> pd.DataFrame:
        """Lê o arquivo de transcrição tratando delimitadores (tabulação/vírgula)

        e normalizando os nomes das colunas.
        """
        # Tenta ler com separador de tabulação (padrão DAIC-WOZ) e fallback para vírgula
        try:
            df = pd.read_csv(transcript_path, sep="\t")
            if len(df.columns) <= 1:
                df = pd.read_csv(transcript_path, sep=",")
        except Exception:
            df = pd.read_csv(transcript_path, sep=",")

        # Limpa espaços em branco dos nomes das colunas
        df.columns = df.columns.str.strip()

        # Normaliza nomes de colunas conhecidos (ex: start_time -> startTime)
        rename_map = {
            "start_time": "startTime",
            "stop_time": "endTime",
            "start": "startTime",
            "stop": "endTime",
            "end": "endTime",
        }
        df.rename(columns=rename_map, inplace=True)

        return df

    def extract_participant_audio_signal(
        self, audio_path: str, transcript_csv_path: str
    ):
        """Carrega o áudio e recorta APENAS os trechos em que o participante está falando."""
        y_full, sr = librosa.load(audio_path, sr=None)

        df = self._read_transcript_dataframe(transcript_csv_path)

        # Valida se as colunas necessárias existem após a normalização
        if "startTime" not in df.columns or "endTime" not in df.columns:
            raise KeyError(
                f"Colunas de tempo não encontradas no arquivo {transcript_csv_path}. "
                f"Colunas disponíveis: {list(df.columns)}"
            )

        # Filtra turnos do participante (case-insensitive)
        speaker_col = "speaker" if "speaker" in df.columns else df.columns[2]
        participant_turns = df[
            df[speaker_col].astype(str).str.lower() == "participant"
        ]

        audio_segments = []
        for _, row in participant_turns.iterrows():
            start_sample = int(float(row["startTime"]) * sr)
            end_sample = int(float(row["endTime"]) * sr)
            audio_segments.append(y_full[start_sample:end_sample])

        if audio_segments:
            y_participant = np.concatenate(audio_segments)
        else:
            y_participant = y_full

        return y_participant, sr

    def extract_acoustic_features(
        self, audio_path: str, transcript_csv_path: str
    ) -> dict:
        """Extrai métricas prosódicas e acústicas usando librosa apenas na voz do participante."""
        y, sr = self.extract_participant_audio_signal(
            audio_path, transcript_csv_path
        )

        # 1. Energia Média (RMS)
        rms = librosa.feature.rms(y=y)[0]
        mean_energy = float(np.mean(rms))

        # 2. Pitch (F0) via piptrack com filtro de voz humana (80-400Hz)
        pitches, magnitudes = librosa.piptrack(y=y, sr=sr)
        indices = magnitudes.argmax(axis=0)
        f0 = np.array(
            [
                pitches[idx, t]
                for t, idx in enumerate(indices)
                if magnitudes[idx, t] > 0.1
            ]
        )
        f0 = f0[(f0 >= 80) & (f0 <= 400)]

        pitch_mean = float(np.mean(f0)) if len(f0) > 0 else 0.0
        pitch_std = float(np.std(f0)) if len(f0) > 0 else 0.0

        # 3. Análise de Silêncio e Pausas
        intervals = librosa.effects.split(y, top_db=25)
        total_duration = len(y) / sr
        speech_duration = (
            sum([(end - start) / sr for start, end in intervals])
            if len(intervals) > 0
            else 0.0
        )
        pause_duration = total_duration - speech_duration
        pause_ratio = (
            float(pause_duration / total_duration) if total_duration > 0 else 0.0
        )

        # 4. Marcadores da Literatura
        acoustic_flags = []
        is_acoustic_anomaly = False

        if pitch_std < PITCH_STD_THRESHOLD:
            is_acoustic_anomaly = True
            acoustic_flags.append(
                "Alta monotonia vocal (desvio padrão de pitch < 20.0 Hz)"
            )

        if pause_ratio > PAUSE_RATIO_THRESHOLD:
            is_acoustic_anomaly = True
            acoustic_flags.append(
                f"Lentificação acentuada da fala (taxa de pausa: {round(pause_ratio * 100, 1)}%)"
            )

        if mean_energy < ENERGY_RMS_THRESHOLD:
            is_acoustic_anomaly = True
            acoustic_flags.append(
                "Voz fraca / baixa energia RMS (indicador de exaustão)"
            )

        return {
            "duration_seconds": round(total_duration, 2),
            "acoustic_metrics": {
                "mean_energy": round(mean_energy, 5),
                "pitch_mean_hz": round(pitch_mean, 2),
                "pitch_std_dev_hz": round(pitch_std, 2),
                "pause_ratio": round(pause_ratio, 3),
            },
            "is_acoustic_anomaly": is_acoustic_anomaly,
            "acoustic_flags": acoustic_flags,
        }

    def analyze_participant_folder(self, folder_path: str) -> dict:
        """Localiza os arquivos .wav e _TRANSCRIPT.csv da pasta e orquestra a análise."""
        participant_id = os.path.basename(folder_path.rstrip("/")).split("_")[0]

        wav_files = glob.glob(os.path.join(folder_path, "*.wav"))
        if not wav_files:
            raise FileNotFoundError(
                f"Nenhum arquivo .wav encontrado em {folder_path}"
            )
        audio_path = wav_files[0]

        transcript_files = glob.glob(
            os.path.join(folder_path, "*_TRANSCRIPT.csv")
        ) or glob.glob(os.path.join(folder_path, "*_TRANSCRIPT.txt"))
        if not transcript_files:
            raise FileNotFoundError(
                f"Nenhum arquivo _TRANSCRIPT encontrado em {folder_path}"
            )
        transcript_path = transcript_files[0]

        # Extrai métricas acústicas fatiando apenas a voz do paciente
        acoustic_res = self.extract_acoustic_features(
            audio_path, transcript_path
        )

        # Carrega a transcrição do participante para o LLM
        df_trans = self._read_transcript_dataframe(transcript_path)
        speaker_col = (
            "speaker" if "speaker" in df_trans.columns else df_trans.columns[2]
        )
        value_col = (
            "value" if "value" in df_trans.columns else df_trans.columns[3]
        )

        participant_df = df_trans[
            df_trans[speaker_col].astype(str).str.lower() == "participant"
        ]
        full_transcript = " ".join(
            participant_df[value_col].dropna().astype(str).tolist()
        )

        return {
            "participant_id": participant_id,
            "duration_seconds": acoustic_res["duration_seconds"],
            "acoustic_metrics": acoustic_res["acoustic_metrics"],
            "is_acoustic_anomaly": acoustic_res["is_acoustic_anomaly"],
            "acoustic_flags": acoustic_res["acoustic_flags"],
            "transcript": full_transcript,
        }