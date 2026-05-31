#include "ParametersFileReader.h"

#include <algorithm>
#include <cctype>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <vector>

namespace fs = std::filesystem;

std::string ParametersFileReader::trim(const std::string& s)
{
    std::size_t b = 0;
    std::size_t e = s.size();
    while (b < e && std::isspace(static_cast<unsigned char>(s[b]))) {
        ++b;
    }
    while (e > b && std::isspace(static_cast<unsigned char>(s[e - 1]))) {
        --e;
    }
    return s.substr(b, e - b);
}

std::string ParametersFileReader::normalizeId(const std::string& s)
{
    std::string out;
    out.reserve(s.size());
    for (unsigned char ch : s) {
        if (ch == ' ' || ch == '_') {
            continue;
        }
        out.push_back(static_cast<char>(std::tolower(ch)));
    }
    return out;
}

ParametersFileReader::ParametersFileReader(std::string folderPath, std::string parametersFileName)
    : m_folderPath(std::move(folderPath)), m_parametersFileName(std::move(parametersFileName))
{
}

void ParametersFileReader::read()
{
    m_surfaceMap.clear();
    m_powerPerPhoton = 0.0;

    m_parametersFilePath = findParametersFile();
    m_photonFilePrefix = inferPhotonFilePrefix(m_parametersFilePath);

    std::ifstream file(m_parametersFilePath);
    if (!file.is_open()) {
        throw std::runtime_error("Unable to open parameters file: " + m_parametersFilePath.string());
    }

    std::string line;
    while (std::getline(file, line)) {
        line = trim(line);
        if (line.empty() || line.rfind("#", 0) == 0) {
            continue;
        }

        if (line == "START PARAMETERS") {
            parseParameterBlock(file);
        } else if (line == "START SURFACES") {
            parseSurfaceBlock(file);
            parsePowerAfterSurfaces(file);
            break;
        }
    }

    if (m_surfaceMap.empty()) {
        std::cerr << "Warning: no surfaces parsed from " << m_parametersFilePath << "\n";
    }
    if (m_powerPerPhoton <= 0.0) {
        std::cerr << "Warning: power per photon not found or non-positive.\n";
    }
}

fs::path ParametersFileReader::findParametersFile() const
{
    if (!fs::exists(m_folderPath) || !fs::is_directory(m_folderPath)) {
        throw std::runtime_error("Input folder does not exist or is not a directory: " + m_folderPath.string());
    }

    if (!m_parametersFileName.empty()) {
        fs::path explicitPath = fs::path(m_parametersFileName);
        if (explicitPath.is_relative()) {
            explicitPath = m_folderPath / explicitPath;
        }
        if (!fs::exists(explicitPath)) {
            throw std::runtime_error("Specified parameters file does not exist: " + explicitPath.string());
        }
        return explicitPath;
    }

    const fs::path legacy = m_folderPath / "photons_parameters.txt";
    if (fs::exists(legacy)) {
        return legacy;
    }

    std::vector<fs::path> candidates;
    for (const auto& entry : fs::directory_iterator(m_folderPath)) {
        if (!entry.is_regular_file()) {
            continue;
        }
        const std::string name = entry.path().filename().string();
        if (name.size() >= 15 && name.rfind("_parameters.txt") == name.size() - 15) {
            candidates.push_back(entry.path());
        }
    }

    if (candidates.empty()) {
        throw std::runtime_error("No *_parameters.txt file found in input folder: " + m_folderPath.string());
    }
    if (candidates.size() > 1) {
        std::string message = "More than one *_parameters.txt file found. Please specify one explicitly:";
        for (const auto& candidate : candidates) {
            message += "\n  " + candidate.filename().string();
        }
        throw std::runtime_error(message);
    }
    return candidates.front();
}

std::string ParametersFileReader::inferPhotonFilePrefix(const fs::path& parametersFilePath)
{
    const std::string filename = parametersFilePath.filename().string();
    const std::string suffix = "_parameters.txt";
    if (filename.size() > suffix.size()
        && filename.rfind(suffix) == filename.size() - suffix.size()) {
        return filename.substr(0, filename.size() - suffix.size());
    }
    return "photons";
}

void ParametersFileReader::parseParameterBlock(std::ifstream& file)
{
    std::vector<std::string> parameterNames;
    std::string line;
    while (std::getline(file, line)) {
        line = trim(line);
        if (line == "END PARAMETERS") {
            break;
        }
        if (!line.empty() && line[0] != '#') {
            parameterNames.push_back(line);
        }
    }

    if (!matchesExpectedParameterList(parameterNames)) {
        throw std::runtime_error("Photon parameter list does not match the currently supported structure: id, x, y, z, side, previous ID, next ID, surface ID.");
    }
}

bool ParametersFileReader::matchesExpectedParameterList(const std::vector<std::string>& actual)
{
    const std::vector<std::string> expected = {
        "id", "x", "y", "z", "side", "previous ID", "next ID", "surface ID"
    };

    if (actual.size() != expected.size()) {
        return false;
    }

    for (std::size_t i = 0; i < expected.size(); ++i) {
        if (normalizeId(actual[i]) != normalizeId(expected[i])) {
            return false;
        }
    }
    return true;
}

void ParametersFileReader::parseSurfaceBlock(std::ifstream& file)
{
    std::string line;
    while (std::getline(file, line)) {
        line = trim(line);
        if (line == "END SURFACES") {
            break;
        }
        if (line.empty() || line[0] == '#') {
            continue;
        }

        std::istringstream iss(line);
        std::uint64_t surfaceId = 0;
        std::string surfacePath;
        if (iss >> surfaceId >> std::ws && std::getline(iss, surfacePath)) {
            m_surfaceMap[surfaceId] = trim(surfacePath);
        }
    }
}

void ParametersFileReader::parsePowerAfterSurfaces(std::ifstream& file)
{
    std::string line;
    std::string lastNumericToken;
    while (std::getline(file, line)) {
        line = trim(line);
        if (line.empty() || line[0] == '#') {
            continue;
        }

        std::istringstream iss(line);
        std::string token;
        while (iss >> token) {
            std::string canon = token;
            std::replace(canon.begin(), canon.end(), ',', '.');
            try {
                std::size_t pos = 0;
                (void)std::stod(canon, &pos);
                if (pos == canon.size()) {
                    lastNumericToken = canon;
                }
            } catch (...) {
            }
        }
    }

    if (lastNumericToken.empty()) {
        throw std::runtime_error("Failed to read power per photon: no numeric token after END SURFACES.");
    }

    m_powerPerPhoton = std::stod(lastNumericToken);
}

const std::unordered_map<std::uint64_t, std::string>& ParametersFileReader::getSurfaceMap() const
{
    return m_surfaceMap;
}

double ParametersFileReader::getPowerPerPhoton() const
{
    return m_powerPerPhoton;
}
