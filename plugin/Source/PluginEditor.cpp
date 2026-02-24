#include "PluginEditor.h"

VINSPluginAudioProcessorEditor::VINSPluginAudioProcessorEditor(VINSPluginAudioProcessor& p)
    : AudioProcessorEditor(&p), processor(p)
{
    titleLabel.setText("VINS Plugin Stub", juce::dontSendNotification);
    titleLabel.setFont(juce::FontOptions(24.0f).withStyle("Bold"));
    titleLabel.setJustificationType(juce::Justification::centredTop);
    addAndMakeVisible(titleLabel);

    bodyLabel.setText(
        "This JUCE scaffold will host the shared Python/Rust transcription engine in a later phase.",
        juce::dontSendNotification);
    bodyLabel.setJustificationType(juce::Justification::centred);
    addAndMakeVisible(bodyLabel);

    setSize(480, 260);
}

VINSPluginAudioProcessorEditor::~VINSPluginAudioProcessorEditor() = default;

void VINSPluginAudioProcessorEditor::paint(juce::Graphics& g)
{
    g.fillAll(juce::Colour::fromRGB(18, 20, 16));
    g.setColour(juce::Colour::fromRGB(18, 128, 109));
    g.drawRoundedRectangle(getLocalBounds().reduced(10).toFloat(), 12.0f, 2.0f);
}

void VINSPluginAudioProcessorEditor::resized()
{
    auto area = getLocalBounds().reduced(18);
    titleLabel.setBounds(area.removeFromTop(50));
    bodyLabel.setBounds(area.removeFromTop(120));
}

