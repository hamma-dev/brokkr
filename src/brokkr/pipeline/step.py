"""
Core classes for the Step-level components of the Pipeline archetecture.
"""

# Standard library imports
import abc
import os
from pathlib import Path

# Local imports
import brokkr.pipeline.base
import brokkr.utils.decode
import brokkr.utils.log
import brokkr.utils.misc
import brokkr.utils.output


# --- Core PipelineStep classes --- #

class PipelineStep(brokkr.pipeline.base.Executable, metaclass=abc.ABCMeta):
    # pylint: disable=abstract-method
    pass


class UnitStep(PipelineStep, metaclass=abc.ABCMeta):
    # pylint: disable=abstract-method
    pass


class InputStep(PipelineStep, metaclass=abc.ABCMeta):
    # pylint: disable=abstract-method
    pass


class TransformStep(PipelineStep, metaclass=abc.ABCMeta):
    # pylint: disable=abstract-method
    pass


class OutputStep(PipelineStep, metaclass=abc.ABCMeta):
    # pylint: disable=abstract-method
    pass


# --- Base input classes --- #

class DecodeInputStep(InputStep, metaclass=abc.ABCMeta):
    def __init__(
            self,
            variables,
            conversion_functions=None,
            custom_types=None,
            variable_default_kwargs=None,
            **pipeline_step_kwargs):
        super().__init__(**pipeline_step_kwargs)
        self.variables = variables
        if variable_default_kwargs is None:
            variable_default_kwargs = {}
        self.decoder = brokkr.utils.decode.DataDecoder(
            variables=self.variables,
            conversion_functions=conversion_functions,
            custom_types=custom_types,
            **variable_default_kwargs,
            )

    @abc.abstractmethod
    def read_raw_data(self):
        pass

    def decode_data(self, raw_data):
        self.logger.debug("Created data decoder: %r", self.decoder)
        decoded_data = self.decoder.decode_data(raw_data)
        return decoded_data

    def execute(self, input_data=None):
        input_data = super().execute(input_data=input_data)
        raw_data = self.read_raw_data()
        output_data = self.decode_data(raw_data)
        return output_data


# --- Base output classes --- #

class FileOutputStep(OutputStep, metaclass=abc.ABCMeta):
    def __init__(
            self,
            output_path=Path(),
            filename_template=None,
            extension=None,
            filename_kwargs=None,
            **pipeline_step_kwargs):
        super().__init__(**pipeline_step_kwargs)
        self.output_path = output_path
        self.filename_template = filename_template
        self.extension = extension
        self.filename_kwargs = (
            {} if filename_kwargs is None else filename_kwargs)

    @abc.abstractmethod
    def write_file(self, input_data, output_file_path):
        pass

    def execute(self, input_data=None):
        input_data = super().execute(input_data=input_data)
        output_file_path = brokkr.utils.output.render_output_filename(
            output_path=self.output_path,
            filename_template=self.filename_template,
            extension=self.extension,
            **self.filename_kwargs)

        self.logger.debug("Ensuring output directory at %r",
                          output_file_path.parent.as_posix())
        os.makedirs(output_file_path.parent, exist_ok=True)
        self.logger.debug("Writing data to file at %r",
                          output_file_path.as_posix())
        try:
            self.write_file(input_data, output_file_path=output_file_path)
            self.logger.debug("Data successfully written to file at %r",
                              output_file_path.as_posix())
            return input_data
        except Exception as e:
            self.logger.error(
                "%s writing output data to file at %r: %s",
                type(e).__name__, output_file_path.as_posix(), e)
            data_repr = repr(input_data)
            if len(data_repr) > 1000:
                data_repr = data_repr[:1000] + " <snipped at 1000 chars>"
            self.log_helper.log(data=data_repr)
            return input_data


# --- Multi-step classes --- #

class MultiStep(PipelineStep, metaclass=abc.ABCMeta):
    # pylint: disable=abstract-method
    def __init__(self, steps, **pipeline_step_kwargs):
        super().__init__(**pipeline_step_kwargs)
        self.steps = steps


class SequentialMultiStep(MultiStep, brokkr.pipeline.base.SequentialMixin):
    def execute(self, input_data=None):
        input_data = super().execute(input_data=input_data)
        output_data = []
        for idx, step in enumerate(self.steps):
            step_output = self.execute_step(idx, step, input_data=input_data)
            if output_data is not None:
                output_data.append(step_output)

        output_data_flat = {}
        for inner_dict in output_data:
            output_data_flat.update(inner_dict)
        return output_data_flat