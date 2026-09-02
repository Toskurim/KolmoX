with open("src/kolmox/engines/extended_domains.py", "r", encoding="utf-8") as f:
    content = f.read()

header = """from .base import BaseDomainEngine
"""

if "from .base import BaseDomainEngine" not in content:
    content = header + content

# Assicuriamo che le classi ereditino formalmente
content = content.replace("class GCodeEngine:", "class GCodeEngine(BaseDomainEngine):")
content = content.replace("class ScientificFloatEngine:", "class ScientificFloatEngine(BaseDomainEngine):")
content = content.replace("class AudioPCMEngine:", "class AudioPCMEngine(BaseDomainEngine):")
content = content.replace("class PointCloudEngine:", "class PointCloudEngine(BaseDomainEngine):")
content = content.replace("class BinaryBCJEngine:", "class BinaryBCJEngine(BaseDomainEngine):")

with open("src/kolmox/engines/extended_domains.py", "w", encoding="utf-8") as f:
    f.write(content)

print("extended_domains.py allineato con BaseDomainEngine!")
