set -x
set -e
scriptdir=`dirname $0`
realdir=`readlink -f ${scriptdir}`
cd "${realdir}"
cd ..

ffmpeg_bin=`which ffmpeg`
blender_bin=`which blender`
blender_bin=`readlink -f "${blender_bin}"`

"${ffmpeg_bin}" -version
"${blender_bin}" --version

# make sure we have required directories
rm -rf tests_output
mkdir -p tests_output/tmp
export PYTHONPATH=tests
export TMPDIR=`readlink -f tests_output/tmp`

coverage_rc_template=`readlink -f tests/coverage.template.rc`
tests_coverage_rc=`readlink -f tests_output/coverage.rc`

python "${realdir}/prepare_coverage.py" --template "${coverage_rc_template}" --output "${tests_coverage_rc}"

export COVERAGE_PROCESS_START="${tests_coverage_rc}"
coverage="python -m coverage"

${coverage} run --append --rcfile="${tests_coverage_rc}" "${realdir}/test_dummy.py"
${coverage} run --append --rcfile="${tests_coverage_rc}" "${realdir}/test_parallel_render.py" test "${blender_bin}" "${ffmpeg_bin}"

${coverage} combine --rcfile="${tests_coverage_rc}"
${coverage} report --rcfile="${tests_coverage_rc}" --show-missing
${coverage} xml --rcfile="${tests_coverage_rc}" -o tests_output/full_coverage.xml
${coverage} xml --rcfile="${tests_coverage_rc}" --omit 'tests/*' -o tests_output/coverage.xml
