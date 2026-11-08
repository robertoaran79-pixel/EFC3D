# Avisos de terceiros

O EFC3D é da RLA LABS e segue a licença PolyForm Noncommercial 1.0.0 (arquivo `LICENSE`). Ele usa bibliotecas de
código aberto de terceiros, cada uma com a própria licença, que continua valendo para ela:

| Biblioteca | Uso no EFC3D | Licença |
|---|---|---|
| three.js (r169) | vista 3D da janela (`app/web/vendor`) | MIT, Copyright 2010-2024 Three.js Authors |
| Manifold (manifold3d) | sólidos e booleanas | Apache 2.0 |
| NumPy | cálculo | BSD 3-Clause |
| SciPy | cálculo e grafos | BSD 3-Clause |
| trimesh | malhas | MIT |
| Shapely | polígonos | BSD 3-Clause |
| scikit-image | imagem e polígonos | BSD 3-Clause |
| Pillow | imagens | MIT-CMU (HPND) |
| pywebview | janela do app | BSD 3-Clause |
| PyInstaller (só nos instaladores) | empacotamento | GPL 2.0 com exceção para o carregador, que permite distribuir o app empacotado com qualquer licença |
| Inno Setup (só no instalador do Windows) | instalador | licença do Inno Setup (uso livre) |

Os pacotes de instalação levam essas bibliotecas como vêm dos autores; os textos das licenças ficam nos
respectivos pacotes dentro do app instalado e nos sites dos projetos.

As peças de corte das juntas (`app/cutters/lib`) são todas próprias (RLA LABS). Nenhuma peça de corte de terceiros
acompanha o EFC3D.
