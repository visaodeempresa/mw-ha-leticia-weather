"""Fontes de dado — módulos PUROS: nenhum deles importa `homeassistant`.

Cada fonte sabe montar a sua URL e interpretar a resposta; quem faz HTTP é o
coordinator, que tem a sessão do HA. Assim os testes rodam sem rede e sem HA
instalado, e os scripts de `tools/` usam exatamente a mesma leitura que a
integração usa — sem uma segunda verdade.
"""
