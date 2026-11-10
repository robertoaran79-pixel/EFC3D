# EFC3D 1.55

**EFC3D (Easy Flexy and Cuts 3D)**: transforma um modelo 3D em um flexi articulado ou em peças que encaixam, prontas
para imprimir. Mac e Windows, tudo no seu computador. A ajuda completa fica dentro do app (botão ❓).

## Instalar
- **Mac:** abra o `EFC3D-1.55-mac-….dmg` e arraste o EFC3D para Aplicativos. Na primeira vez, clique com o botão
  direito no EFC3D e escolha **Abrir** (o macOS pede essa confirmação para apps baixados fora da App Store).
- **Windows:** rode o `EFC3D-1.55-windows-instalador.exe` e siga os passos. O app fica no menu Iniciar.
- **Pelo código (opcional):** com Python 3.10 a 3.13, `bash install.sh` no Mac ou `instalar_windows.bat` no Windows.

## Requisitos
| | Mínimo | Recomendado |
|---|---|---|
| Sistema | Windows 10 ou 11 (64 bits) com WebView2; macOS 11 | Windows 11; macOS 13 ou mais novo |
| Processador | 4 núcleos, 64 bits (Intel Core i5 de 8ª geração, AMD Ryzen 3000, Mac Intel de 2017, qualquer Apple Silicon) | 6 núcleos ou mais, ou Apple Silicon |
| Memória | 8 GB | 16 GB |
| Placa de vídeo | aceleração 3D ligada e driver atualizado; a integrada serve (Intel UHD 620, Iris Xe, AMD Radeon Vega) | integrada recente ou dedicada (NVIDIA ou AMD) |
| Tela | 1366 × 768 | 1920 × 1080 |

Acesso remoto (Área de Trabalho Remota, AnyDesk) e máquina virtual quase sempre desenham o 3D sem a placa de vídeo e
ficam lentos. O app avisa com "⚠ 3D sem placa de vídeo"; o que fazer está na ajuda, em Desempenho e requisitos.

## Desinstalar
- **Mac:** arraste o EFC3D de Aplicativos para o Lixo.
- **Windows:** Configurações › Aplicativos › EFC3D › Desinstalar.
- Seus arquivos ficam onde estão: configurações em `~/EFC3D` e saídas em `Documentos/EFC3D/saidas`.

## Primeiro modelo
1. **Modelo:** abra um STL, GLB, OBJ ou .zip (ou arraste para a janela).
2. **Juntas:** clique onde o modelo deve dobrar e confira o semáforo de cada junta.
3. **Cores:** pinte as áreas com pincel, balde ou faixa de altura.
4. **Cortes:** separe as áreas pintadas por cor, desenhe cortes livres ou use o corte plano.
5. **Exportar:** um botão gera o 3MF, os STLs e as placas para a sua impressora.

## Novidades da 1.55
Veja o [CHANGELOG](CHANGELOG.md).

## Licença
PolyForm Noncommercial 1.0.0 (arquivo `LICENSE`): livre para uso pessoal e sem fins comerciais.
