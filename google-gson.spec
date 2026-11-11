Name:		google-gson
Version:	2.15.0
Release:	2
Summary:	Java library for converting objects to JSON and back
Group:		Development/Java
License:	ASL 2.0
URL:		https://github.com/google/gson
Source0:	https://github.com/google/gson/archive/refs/tags/gson-parent-%{version}.tar.gz#/gson-%{version}.tar.gz
# Gradle 9.9.1 strictly pins 2.14.0. The tag archive has no prebuilt jars.
Source1:	https://github.com/google/gson/archive/refs/tags/gson-parent-2.14.0.tar.gz#/gson-2.14.0.tar.gz

BuildArch:	noarch
Obsoletes:	%{name}-javadoc < %{version}
BuildRequires:	mvn(com.google.errorprone:error_prone_annotations)
# Literal, so the first rpmbuild -bs records them before sysjar is installed.
BuildRequires:	maven
BuildRequires:	java-current-devel
BuildSystem:	maven
BuildOption(install):	--file-name gson --link %{name}

%description
Gson converts Java objects to JSON and back. 2.15.0 adds
JsonReader.getCharacterOffset, uses LinkedHashMap as the default map,
and accepts only numeric IP addresses for InetAddress. The Error Prone
checker is not packaged, so the parent build is not used. The annotation
jar stays a normal dependency. Tests are skipped. %{version} stays
the default jar. Gradle 9.9.1 strictly pins 2.14.0, so that jar is
installed beside it.

%prep
%autosetup -n gson-gson-parent-%{version}
# gson-parent requires the Error Prone compiler, which is not packaged,
# and pins a jar plugin manifest produced by bnd. Build the gson module
# on its own. Its module-info requires com.google.errorprone.annotations,
# but the system jar is an automatic module named error.prone.annotations,
# so the descriptor is left out and the jar name is set in the manifest.
python - <<'PY'
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

NS = "http://maven.apache.org/POM/4.0.0"
ET.register_namespace("", NS)
ET.register_namespace("xsi", "http://www.w3.org/2001/XMLSchema-instance")

def local(tag):
    return tag.rsplit("}", 1)[-1]

def q(elem, name):
    if elem.tag.startswith("{"):
        return "{" + elem.tag[1:].split("}", 1)[0] + "}" + name
    return name

def find_child(parent, name):
    if parent is None:
        return None
    for child in parent:
        if local(child.tag) == name:
            return child
    return None

def artifact_of(elem):
    node = find_child(elem, "artifactId")
    return (node.text or "").strip() if node is not None else ""

def insert_after(parent, after_name, elem):
    for index, child in enumerate(list(parent)):
        if local(child.tag) == after_name:
            parent.insert(index + 1, elem)
            return
    parent.insert(0, elem)

tree = ET.parse("gson/pom.xml")
root = tree.getroot()
parent = find_child(root, "parent")
if parent is None:
    raise SystemExit("parent missing")
root.remove(parent)

group = ET.Element(q(root, "groupId"))
group.text = "com.google.code.gson"
insert_after(root, "modelVersion", group)
version = ET.Element(q(root, "version"))
version.text = "%{version}"
insert_after(root, "artifactId", version)

props = find_child(root, "properties")
if props is None:
    raise SystemExit("properties missing")
release = ET.Element(q(props, "maven.compiler.release"))
release.text = "8"
props.insert(0, release)

drop_plugins = {
    "templating-maven-plugin",
    "bnd-maven-plugin",
    "maven-surefire-plugin",
    "maven-failsafe-plugin",
    "proguard-maven-plugin",
    "moditect-maven-plugin",
    "maven-javadoc-plugin",
    "central-publishing-maven-plugin",
    "maven-resources-plugin",
    "maven-compiler-plugin",
}
removed = set()
for plugins in list(root.iter()):
    if local(plugins.tag) != "plugins":
        continue
    for plugin in list(plugins):
        if local(plugin.tag) != "plugin":
            continue
        name = artifact_of(plugin)
        if name in drop_plugins:
            plugins.remove(plugin)
            removed.add(name)
missing = drop_plugins - removed
if missing:
    raise SystemExit("plugins not removed: " + " ".join(sorted(missing)))

jar = None
for plugins in root.iter():
    if local(plugins.tag) != "plugins":
        continue
    for plugin in plugins:
        if local(plugin.tag) == "plugin" and artifact_of(plugin) == "maven-jar-plugin":
            jar = plugin
if jar is None:
    raise SystemExit("jar plugin missing")
jar_version = find_child(jar, "version")
if jar_version is None:
    jar_version = ET.Element(q(jar, "version"))
    insert_after(jar, "artifactId", jar_version)
jar_version.text = "3.5.1"
for item in list(jar):
    if local(item.tag) == "configuration":
        jar.remove(item)
conf = ET.SubElement(jar, q(jar, "configuration"))
archive = ET.SubElement(conf, q(jar, "archive"))
entries = ET.SubElement(archive, q(jar, "manifestEntries"))
automatic = ET.SubElement(entries, q(jar, "Automatic-Module-Name"))
automatic.text = "com.google.gson"

deps = find_child(root, "dependencies")
if deps is None:
    raise SystemExit("dependencies missing")
kept_dep = False
for dep in list(deps):
    if local(dep.tag) != "dependency":
        continue
    scope = find_child(dep, "scope")
    if scope is not None and (scope.text or "").strip() == "test":
        deps.remove(dep)
        continue
    if artifact_of(dep) == "error_prone_annotations":
        kept_dep = True
if not kept_dep:
    raise SystemExit("error_prone_annotations dependency missing")

profiles = find_child(root, "profiles")
if profiles is not None:
    root.remove(profiles)

tree.write("pom.xml", encoding="UTF-8", xml_declaration=True)
text = Path("pom.xml").read_text(encoding="utf-8")
for banned in ("gson-parent", "moditect", "templating-maven-plugin", "bnd-maven-plugin", "manifestFile", "error_prone_core"):
    if banned in text:
        raise SystemExit("left behind: " + banned)
if "com.google.gson" not in text or "error_prone_annotations" not in text:
    raise SystemExit("flattened pom is incomplete")

if Path("src").exists():
    raise SystemExit("src already exists")
shutil.move("gson/src", "src")
template = Path("src/main/java-templates/com/google/gson/internal/GsonBuildConfig.java")
body = template.read_text(encoding="utf-8")
body = body.replace("${project.version}", "%{version}")
if "${" in body:
    raise SystemExit("placeholder left")
dest = Path("src/main/java/com/google/gson/internal/GsonBuildConfig.java")
if dest.exists():
    raise SystemExit("build config already exists")
dest.write_text(body, encoding="utf-8")
module_info = Path("src/main/java/module-info.java")
if not module_info.is_file():
    raise SystemExit("module-info missing")
module_info.unlink()

for path in Path(".").rglob("pom.xml"):
    if path.resolve() != Path("pom.xml").resolve():
        path.unlink()
PY
%setup -q -T -D -a 1 -n gson-gson-parent-%{version}
find gson-gson-parent-2.14.0 \( -name '*.jar' -o -name '*.class' -o -name '*.so' -o -name '*.node' -o -name '*.wasm' \) -delete
python - <<'PY'
from pathlib import Path
root = Path("gson-gson-parent-2.14.0/gson")
template = root / "src/main/java-templates/com/google/gson/internal/GsonBuildConfig.java"
text = template.read_text(encoding="utf-8").replace("${project.version}", "2.14.0")
if "${" in text:
    raise SystemExit("placeholder left")
dest = root / "src/main/java/com/google/gson/internal/GsonBuildConfig.java"
dest.write_text(text, encoding="utf-8")
module_info = root / "src/main/java/module-info.java"
if module_info.is_file():
    module_info.unlink()
PY

%build -a
export JAVA_HOME="${JAVA_HOME:-%{_jvmdir}/java-openjdk}"
export PATH="$JAVA_HOME/bin:$PATH"
mkdir -p gson214/classes
find gson-gson-parent-2.14.0/gson/src/main/java -name '*.java' > gson214/sources.list
test -s gson214/sources.list
javac --release 8 -encoding UTF-8 -Xlint:-options \
	-cp %{_javadir}/error_prone_annotations.jar \
	-d gson214/classes @gson214/sources.list
jar cf gson214/gson.jar -C gson214/classes .
cat > gson214/gson.pom << 'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<project xmlns="http://maven.apache.org/POM/4.0.0">
  <modelVersion>4.0.0</modelVersion>
  <groupId>com.google.code.gson</groupId>
  <artifactId>gson</artifactId>
  <version>2.14.0</version>
  <name>Gson</name>
  <description>Java library for converting objects to JSON and back.</description>
  <url>https://github.com/google/gson</url>
  <licenses>
    <license>
      <name>Apache-2.0</name>
      <url>https://www.apache.org/licenses/LICENSE-2.0.txt</url>
    </license>
  </licenses>
  <dependencies>
    <dependency>
      <groupId>com.google.errorprone</groupId>
      <artifactId>error_prone_annotations</artifactId>
      <version>2.50.0</version>
    </dependency>
  </dependencies>
</project>
EOF

%install -p
sysjar install --buildroot %{buildroot} \
	--artifact gson214/gson.pom:gson214/gson.jar \
	--file-name gson-2.14.0 \
	--filelist .mfiles214
# %{version} owns gson.sysjar. 2.14.0 keeps a second index file.
/bin/mv %{buildroot}/usr/share/sysjar/index/com.google.code.gson/gson.sysjar \
	%{buildroot}/usr/share/sysjar/index/com.google.code.gson/gson-2.14.0.sysjar
sed -i 's|/usr/share/sysjar/index/com.google.code.gson/gson\.sysjar|/usr/share/sysjar/index/com.google.code.gson/gson-2.14.0.sysjar|' .mfiles214

%install -a
while IFS= read -r line; do
	grep -qxF -- "$line" .mfiles || printf '%s\n' "$line" >> .mfiles
done < .mfiles214

%check
export JAVA_HOME="${JAVA_HOME:-%{_jvmdir}/java-openjdk}"
export PATH="$JAVA_HOME/bin:$PATH"
cat > GsonSmoke.java << 'EOF'
import com.google.gson.Gson;
public class GsonSmoke {
	public static void main(String[] args) {
		Gson gson = new Gson();
		String json = gson.toJson(Integer.valueOf(42));
		int n = gson.fromJson(json, Integer.class).intValue();
		if (n != 42) {
			throw new AssertionError(json);
		}
		System.out.println(args[0] + " " + n);
	}
}
EOF
javac --release 8 -encoding UTF-8 -Xlint:-options \
	-cp "%{buildroot}%{_javadir}/gson.jar:%{_javadir}/error_prone_annotations.jar" \
	-d . GsonSmoke.java
java -cp "%{buildroot}%{_javadir}/gson.jar:%{_javadir}/error_prone_annotations.jar:." GsonSmoke gson215_ok > check215.log
cat check215.log
grep -F -q 'gson215_ok 42' check215.log
javac --release 8 -encoding UTF-8 -Xlint:-options \
	-cp "%{buildroot}%{_javadir}/gson-2.14.0.jar:%{_javadir}/error_prone_annotations.jar" \
	-d . GsonSmoke.java
java -cp "%{buildroot}%{_javadir}/gson-2.14.0.jar:%{_javadir}/error_prone_annotations.jar:." GsonSmoke gson214_ok > check214.log
cat check214.log
grep -F -q 'gson214_ok 42' check214.log

%files -f .mfiles
%doc LICENSE README.md CHANGELOG.md
