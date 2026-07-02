import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.plasma.plasmoid
import org.kde.plasma.components as PlasmaComponents3
import org.kde.plasma.plasma5support as Plasma5Support
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    readonly property string schedctl: "python3 $HOME/Projects/Personal/brightness-scheduler/scheduler/schedctl.py"
    readonly property var anchorLabels: ({
        night: "Noc",
        sunrise: "Východ slunce",
        noon: "Poledne",
        sunset: "Západ slunce"
    })

    property bool automationEnabled: true
    property var monitorsData: ({})
    property var sunTimes: ({})

    Plasma5Support.DataSource {
        id: exec
        engine: "executable"
        connectedSources: []
        onNewData: (sourceName, data) => {
            disconnectSource(sourceName)
            if (sourceName.indexOf("get-status") !== -1) {
                try {
                    const parsed = JSON.parse(data["stdout"])
                    root.automationEnabled = parsed.enabled
                    root.monitorsData = parsed.monitors
                    root.sunTimes = parsed.times
                } catch (e) {
                    console.log("brightness-scheduler: failed to parse status", e, data["stdout"])
                }
            }
        }

        function run(cmd) {
            connectSource(cmd)
        }

        function refreshStatus() {
            run(root.schedctl + " get-status")
        }
    }

    Component.onCompleted: exec.refreshStatus()

    preferredRepresentation: compactRepresentation

    compactRepresentation: Kirigami.Icon {
        source: "video-display-brightness-symbolic"
        Layout.fillWidth: false
        Layout.fillHeight: false
        Layout.minimumWidth: Kirigami.Units.iconSizes.small
        Layout.minimumHeight: Kirigami.Units.iconSizes.small
        Layout.preferredWidth: Kirigami.Units.iconSizes.small
        Layout.preferredHeight: Kirigami.Units.iconSizes.small
        Layout.maximumWidth: Kirigami.Units.iconSizes.small
        Layout.maximumHeight: Kirigami.Units.iconSizes.small
        MouseArea {
            anchors.fill: parent
            onClicked: root.expanded = !root.expanded
        }
    }

    fullRepresentation: PlasmaComponents3.ScrollView {
        implicitWidth: Kirigami.Units.gridUnit * 22
        implicitHeight: Kirigami.Units.gridUnit * 26
        Layout.preferredWidth: Kirigami.Units.gridUnit * 22
        Layout.preferredHeight: Kirigami.Units.gridUnit * 26

        ColumnLayout {
            width: parent.width
            spacing: Kirigami.Units.smallSpacing

            RowLayout {
                Layout.fillWidth: true
                Layout.margins: Kirigami.Units.smallSpacing
                PlasmaComponents3.Label {
                    text: "Automatický jas podle Slunce (Praha)"
                    font.bold: true
                    Layout.fillWidth: true
                }
                PlasmaComponents3.Switch {
                    checked: root.automationEnabled
                    onToggled: {
                        root.automationEnabled = checked
                        exec.run(root.schedctl + " set-enabled " + (checked ? "true" : "false"))
                    }
                }
            }

            Kirigami.Separator { Layout.fillWidth: true }

            Repeater {
                model: Object.keys(root.monitorsData)
                delegate: ColumnLayout {
                    id: monitorBlock
                    Layout.fillWidth: true
                    Layout.margins: Kirigami.Units.smallSpacing
                    required property string modelData
                    property string monitorKey: modelData
                    property var monitor: root.monitorsData[monitorKey]

                    PlasmaComponents3.Label {
                        text: monitorBlock.monitor.label
                        font.bold: true
                    }

                    Repeater {
                        model: ["night", "sunrise", "noon", "sunset"]
                        delegate: RowLayout {
                            id: anchorRow
                            Layout.fillWidth: true
                            required property string modelData
                            property string anchorKey: modelData
                            property string timeHint: root.sunTimes[anchorKey] || ""

                            PlasmaComponents3.Label {
                                Layout.preferredWidth: Kirigami.Units.gridUnit * 7
                                text: root.anchorLabels[anchorRow.anchorKey] +
                                      (anchorRow.timeHint ? " (" + anchorRow.timeHint + ")" : "")
                            }
                            PlasmaComponents3.Slider {
                                id: slider
                                Layout.fillWidth: true
                                from: 0
                                to: 100
                                stepSize: 1
                                value: monitorBlock.monitor.anchors[anchorRow.anchorKey]
                                onMoved: {
                                    exec.run(root.schedctl + " preview " + monitorBlock.monitorKey + " " + Math.round(value))
                                }
                                onPressedChanged: {
                                    if (!pressed) {
                                        exec.run(root.schedctl + " set-anchor " + monitorBlock.monitorKey + " " +
                                                 anchorRow.anchorKey + " " + Math.round(value))
                                    }
                                }
                            }
                            PlasmaComponents3.Label {
                                Layout.preferredWidth: Kirigami.Units.gridUnit * 2
                                text: Math.round(slider.value) + "%"
                                horizontalAlignment: Text.AlignRight
                            }
                        }
                    }

                    Kirigami.Separator { Layout.fillWidth: true }
                }
            }

            PlasmaComponents3.Button {
                Layout.alignment: Qt.AlignRight
                Layout.margins: Kirigami.Units.smallSpacing
                text: "Obnovit"
                icon.name: "view-refresh"
                onClicked: exec.refreshStatus()
            }
        }
    }
}
