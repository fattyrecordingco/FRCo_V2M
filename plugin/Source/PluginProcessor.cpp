#include "PluginProcessor.h"
#include "PluginEditor.h"

#include <cmath>

namespace
{
juce::AudioProcessorValueTreeState::ParameterLayout makeLayout()
{
    std::vector<std::unique_ptr<juce::RangedAudioParameter>> params;
    params.push_back(std::make_unique<juce::AudioParameterFloat>("mix", "Mix", 0.0f, 1.0f, 1.0f));
    params.push_back(std::make_unique<juce::AudioParameterBool>("passthrough", "Passthrough", true));
    return { params.begin(), params.end() };
}
} // namespace

VINSPluginAudioProcessor::VINSPluginAudioProcessor()
    : AudioProcessor(BusesProperties().withInput("Input", juce::AudioChannelSet::stereo(), true)
                                         .withOutput("Output", juce::AudioChannelSet::stereo(), true)),
      parameters(*this, nullptr, "PARAMETERS", makeLayout())
{
}

VINSPluginAudioProcessor::~VINSPluginAudioProcessor() = default;

void VINSPluginAudioProcessor::prepareToPlay(double sampleRate, int)
{
    currentSampleRate = sampleRate > 0.0 ? sampleRate : 44100.0;
    gateOpen = false;
    lastMidiNote = -1;
    lastExpression = -1;
    lastBrightness = -1;
}

void VINSPluginAudioProcessor::releaseResources() {}

bool VINSPluginAudioProcessor::isBusesLayoutSupported(const BusesLayout& layouts) const
{
    return layouts.getMainInputChannelSet() == layouts.getMainOutputChannelSet();
}

void VINSPluginAudioProcessor::processBlock(juce::AudioBuffer<float>& buffer, juce::MidiBuffer& midiMessages)
{
    juce::ScopedNoDenormals noDenormals;
    const auto* mixParam = parameters.getRawParameterValue("mix");
    const auto* passParam = parameters.getRawParameterValue("passthrough");
    const float mix = mixParam != nullptr ? mixParam->load() : 1.0f;
    const bool passthrough = passParam != nullptr ? passParam->load() > 0.5f : true;

    if (!passthrough)
    {
        buffer.clear();
        return;
    }

    if (mix < 0.999f)
    {
        for (int channel = 0; channel < buffer.getNumChannels(); ++channel)
        {
            buffer.applyGain(channel, 0, buffer.getNumSamples(), mix);
        }
    }

    emitVoiceControllerMidi(buffer, midiMessages);
}

juce::AudioProcessorEditor* VINSPluginAudioProcessor::createEditor()
{
    return new VINSPluginAudioProcessorEditor(*this);
}

void VINSPluginAudioProcessor::getStateInformation(juce::MemoryBlock& destData)
{
    if (auto xml = parameters.state.createXml())
    {
        copyXmlToBinary(*xml, destData);
    }
}

void VINSPluginAudioProcessor::setStateInformation(const void* data, int sizeInBytes)
{
    if (auto xml = getXmlFromBinary(data, sizeInBytes))
    {
        parameters.state = juce::ValueTree::fromXml(*xml);
    }
}

juce::AudioProcessor* JUCE_CALLTYPE createPluginFilter()
{
    return new VINSPluginAudioProcessor();
}

void VINSPluginAudioProcessor::emitVoiceControllerMidi(const juce::AudioBuffer<float>& buffer, juce::MidiBuffer& midiMessages)
{
    if (buffer.getNumSamples() <= 0 || currentSampleRate <= 0.0)
        return;

    const float envelope = estimateEnvelope(buffer);
    const float brightness = estimateBrightness(buffer);
    const int expression = juce::jlimit(0, 127, static_cast<int>(std::round(envelope * 900.0f)));
    const int brightnessCc = juce::jlimit(0, 127, static_cast<int>(std::round(brightness * 127.0f)));

    if (std::abs(expression - lastExpression) >= 2)
    {
        midiMessages.addEvent(juce::MidiMessage::controllerEvent(1, 11, expression), 0);
        lastExpression = expression;
    }
    if (std::abs(brightnessCc - lastBrightness) >= 2)
    {
        midiMessages.addEvent(juce::MidiMessage::controllerEvent(1, 74, brightnessCc), 0);
        lastBrightness = brightnessCc;
    }

    const float gateThreshold = 0.035f;
    if (envelope < gateThreshold)
    {
        if (gateOpen && lastMidiNote >= 0)
        {
            midiMessages.addEvent(juce::MidiMessage::noteOff(1, lastMidiNote), 0);
        }
        gateOpen = false;
        lastMidiNote = -1;
        return;
    }

    const float freqHz = estimateFrequency(buffer);
    if (freqHz < 50.0f || freqHz > 1800.0f)
        return;

    const float midiValue = 69.0f + 12.0f * std::log2(freqHz / 440.0f);
    const int midiNote = juce::jlimit(24, 108, static_cast<int>(std::round(midiValue)));

    if (!gateOpen || midiNote != lastMidiNote)
    {
        if (gateOpen && lastMidiNote >= 0)
            midiMessages.addEvent(juce::MidiMessage::noteOff(1, lastMidiNote), 0);
        midiMessages.addEvent(juce::MidiMessage::noteOn(1, midiNote, juce::uint8(juce::jlimit(24, 127, expression))), 0);
        gateOpen = true;
        lastMidiNote = midiNote;
    }

    const float bendSemitones = juce::jlimit(-2.0f, 2.0f, midiValue - static_cast<float>(midiNote));
    const int bendValue = juce::jlimit(0, 16383, 8192 + static_cast<int>(std::round((bendSemitones / 2.0f) * 8191.0f)));
    midiMessages.addEvent(juce::MidiMessage::pitchWheel(1, bendValue), 0);
}

float VINSPluginAudioProcessor::estimateEnvelope(const juce::AudioBuffer<float>& buffer) const
{
    double sumSquares = 0.0;
    const int channelCount = juce::jmax(1, buffer.getNumChannels());
    for (int sample = 0; sample < buffer.getNumSamples(); ++sample)
    {
        float mono = 0.0f;
        for (int channel = 0; channel < buffer.getNumChannels(); ++channel)
            mono += buffer.getSample(channel, sample);
        mono /= static_cast<float>(channelCount);
        sumSquares += static_cast<double>(mono * mono);
    }
    return static_cast<float>(std::sqrt(sumSquares / juce::jmax(1, buffer.getNumSamples())));
}

float VINSPluginAudioProcessor::estimateBrightness(const juce::AudioBuffer<float>& buffer) const
{
    double totalDelta = 0.0;
    double totalAbs = 0.0;
    const int channelCount = juce::jmax(1, buffer.getNumChannels());
    float previous = 0.0f;
    for (int sample = 0; sample < buffer.getNumSamples(); ++sample)
    {
        float mono = 0.0f;
        for (int channel = 0; channel < buffer.getNumChannels(); ++channel)
            mono += buffer.getSample(channel, sample);
        mono /= static_cast<float>(channelCount);
        totalDelta += std::abs(mono - previous);
        totalAbs += std::abs(mono);
        previous = mono;
    }
    if (totalAbs <= 1.0e-9)
        return 0.0f;
    return juce::jlimit(0.0f, 1.0f, static_cast<float>(totalDelta / (totalAbs * 1.8)));
}

float VINSPluginAudioProcessor::estimateFrequency(const juce::AudioBuffer<float>& buffer) const
{
    int zeroCrossings = 0;
    const int channelCount = juce::jmax(1, buffer.getNumChannels());
    float previous = 0.0f;
    for (int sample = 0; sample < buffer.getNumSamples(); ++sample)
    {
        float mono = 0.0f;
        for (int channel = 0; channel < buffer.getNumChannels(); ++channel)
            mono += buffer.getSample(channel, sample);
        mono /= static_cast<float>(channelCount);
        if ((previous <= 0.0f && mono > 0.0f) || (previous >= 0.0f && mono < 0.0f))
            ++zeroCrossings;
        previous = mono;
    }
    if (zeroCrossings < 2)
        return 0.0f;
    return static_cast<float>((zeroCrossings * currentSampleRate) / (2.0 * buffer.getNumSamples()));
}
