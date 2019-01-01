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

mkdir -p tests_output/tmp
export PYTHONPATH=tests
export TMPDIR=`readlink -f tests_output/tmp`

python "${realdir}/test_parallel_render.py" test "${blender_bin}" "${ffmpeg_bin}"
